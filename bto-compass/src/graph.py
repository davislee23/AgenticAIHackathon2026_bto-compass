import json
import pandas as pd
from pathlib import Path
from typing import Any
from langgraph.graph import StateGraph, END

from src.state import BTOState
from src.engine import score_project, calculate_ehg_grant
from src.config import DATA_PATH_CSV, DATA_PATH_JSON, get_llm
from src.rag.rag_retriever import retrieve_policy
from src.tools.tools import (
    find_bto_flats, 
    search_hdb_policies, 
    calculate_cpf_housing_grant
)

# Initialize LLM & tools
llm = get_llm()
tools = [find_bto_flats, search_hdb_policies, calculate_cpf_housing_grant]

def extract_raw_text(json_data: Any) -> str:
    """Recursively extracts scraped text from various scraper JSON formats."""
    if isinstance(json_data, str):
        return json_data
    if isinstance(json_data, dict):
        for key in ["full_page_content", "markdown", "text", "content", "raw_content"]:
            if key in json_data and isinstance(json_data[key], str):
                return json_data[key]
        if "data" in json_data:
            return extract_raw_text(json_data["data"])
        return json.dumps(json_data, indent=2)
    if isinstance(json_data, list):
        return json.dumps(json_data, indent=2)
    return ""

def profile_validation(state: BTOState):
    print("[Node] profile_validation: Checking applicant constraints...")
    return {}

def load_projects(state: BTOState):
    print("[Node] load_projects: Loading dataset and application rates...")
    
    # Directly target bto-compass/data/application_rates.json from project root
    base_dir = Path(__file__).resolve().parent.parent
    json_path = base_dir / "data" / "application_rates.json"
    
    # Fallback to config path if root file doesn't exist
    if not json_path.exists() and Path(DATA_PATH_JSON).exists():
        json_path = Path(DATA_PATH_JSON)

    csv_path = base_dir / "data" / "bto_projects.csv"
    if not csv_path.exists() and Path(DATA_PATH_CSV).exists():
        csv_path = Path(DATA_PATH_CSV)

    # 1. Load CSV
    try:
        df = pd.read_csv(csv_path) if csv_path.exists() else pd.DataFrame()
        print(f"[Debug] Loaded CSV from {csv_path}")
    except Exception as e:
        print(f"[Error] Failed reading CSV at {csv_path}: {e}")
        df = pd.DataFrame()

    # 2. Load JSON rates and raw content
    rates_dict = {}
    raw_web_content = ""

    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                json_data = json.load(f)

            raw_web_content = extract_raw_text(json_data)

            if isinstance(json_data, dict):
                for key, val in json_data.items():
                    if isinstance(val, (int, float)):
                        rates_dict[key] = float(val)
            elif isinstance(json_data, list):
                for row in json_data:
                    projects_str = row.get("projects_in_group")
                    rate = row.get("application_rate")
                    if projects_str and pd.notna(rate):
                        for name in str(projects_str).split(";"):
                            rates_dict[name.strip()] = float(rate)

            print(f"[Debug] Successfully loaded JSON from {json_path}")
            print(f"[Debug] Extracted raw text length: {len(raw_web_content)} characters")

        except Exception as e:
            print(f"[Warning] Could not load application rates JSON: {e}")
    else:
        print(f"[Warning] JSON file not found at {json_path}")

    return {
        "projects": df.to_dict(orient="records"),
        "application_rates": rates_dict,
        "rates_raw_text": raw_web_content
    }

def filter_projects(state: BTOState):
    print("[Node] filter_projects: Applying budget, grant, and wait time limits...")
    applicant = state.get("applicant") or {}
    
    income = float(applicant.get("monthly_income", 0.0))
    applicant_type = str(applicant.get("applicant_type", "Couple")).strip().title()
    is_single = (applicant_type == "Single")
    
    grant = calculate_ehg_grant(income, is_single=is_single)
    
    budget = applicant.get("budget")
    if budget is None or budget <= 0:
        budget = 2000000.0
    else:
        budget = float(budget)
        
    effective_budget = budget + grant
    
    max_wait = applicant.get("max_wait")
    if max_wait is None or max_wait <= 0:
        max_wait = 10.0
    else:
        max_wait = float(max_wait)
    
    df = pd.DataFrame(state.get("projects", []))
    if df.empty:
        return {"eligible_projects": []}
    
    price_col = "price_min_sgd" if "price_min_sgd" in df.columns else "price_max_sgd"
    if price_col in df.columns:
        budget_filtered = df[df[price_col] <= effective_budget]
    else:
        budget_filtered = df

    if "waiting_time_months" in budget_filtered.columns:
        eligible = budget_filtered[(budget_filtered["waiting_time_months"] / 12.0) <= max_wait]
    else:
        eligible = budget_filtered
    
    return {"eligible_projects": eligible.to_dict(orient="records")}

def get_matching_rate(project_name: str, rates_dict: dict) -> float:
    """Fuzzy matching to associate CSV project names with JSON rate keys."""
    if not rates_dict:
        return 1.0
    p_clean = str(project_name).lower().strip()
    
    for key, rate in rates_dict.items():
        k_clean = str(key).lower().strip()
        if p_clean in k_clean or k_clean in p_clean:
            return float(rate)
    return 1.0

def rank_projects(state: BTOState):
    print("[Node] rank_projects: Computing deterministic scores...")
    applicant = state.get("applicant") or {}
    eligible_projects = state.get("eligible_projects", [])
    
    if not eligible_projects:
        return {"rankings": []}
        
    df = pd.DataFrame(eligible_projects)
    rates = state.get("application_rates", {})
    
    scores = []
    for _, row in df.iterrows():
        project_name = row.get("project_name", "Unknown")
        rate = get_matching_rate(project_name, rates)
        res = score_project(row, rate, applicant)
        if res is not None:
            scores.append(res)
    
    if not scores:
        return {"rankings": []}

    ranked_df = pd.DataFrame(scores).sort_values(by="Total Score", ascending=False).head(3)
    return {"rankings": ranked_df.to_dict(orient="records")}

def generate_explanation(state: BTOState):
    print("[Node] generate_explanation: Retrieving context and prompting LLM...")
    applicant = state.get("applicant") or {}
    rankings = state.get("rankings", [])
    messages = state.get("messages", [])
    rates_raw_text = state.get("rates_raw_text", "")
    rates_dict = state.get("application_rates", {})
    
    user_query = ""
    if messages:
        last_msg = messages[-1]
        if hasattr(last_msg, "content"):
            user_query = last_msg.content
        elif isinstance(last_msg, dict):
            user_query = last_msg.get("content", "")
        elif isinstance(last_msg, str):
            user_query = str(last_msg)

    if not user_query:
        user_query = "Provide recommendations for my BTO application."

    rankings_str = pd.DataFrame(rankings).to_string(index=False) if rankings else "No matching projects found."
    
    applicant_type = applicant.get("applicant_type", "single")
    budget = applicant.get("budget", "N/A")
    max_wait = applicant.get("max_wait", "N/A")
    monthly_income = applicant.get("monthly_income", 0.0)
    
    if rates_raw_text and len(rates_raw_text.strip()) > 0:
        scraped_rates_context = rates_raw_text
    elif rates_dict:
        scraped_rates_context = json.dumps(rates_dict, indent=2)
    else:
        scraped_rates_context = "No application rate data was loaded."

    policy_context = retrieve_policy(user_query, top_k=2)
    
    prompt = f"""
    You are an expert Singapore housing advisor specialized in Singapore HDB housing, BTO flats, CPF grants, and applicant eligibility.

    USER'S QUESTION:
    "{user_query}"

    APPLICANT PROFILE:
    - Household Monthly Income: ${monthly_income:,.2f} SGD
    - Applicant Type: {applicant_type}
    - Max Budget: SGD {budget}
    - Max Wait Time: {max_wait} years
    - First-Timer: {applicant.get('is_first_timer', True)}

    COMPUTED BTO RECOMMENDATIONS:
    {rankings_str}

    LATEST HDB BTO APPLICATION RATES & WEBPAGE DATA:
    {scraped_rates_context}

    HDB POLICY REFERENCE:
    {policy_context}

    INSTRUCTIONS:
    1. Direct Answer: Answer the USER's QUESTION directly in the first sentence.
    2. STRICT DOMAIN GUARDRAIL: Check if the user's question is related to Singapore housing, HDB/BTO flats, CPF grants, home buying, or applicant eligibility. 
       - If the query is OUT OF SCOPE (e.g., cooking, programming, general trivia, stock advice, unrelated topics), politely refuse: "I am BTO Compass, a specialized Singapore housing assistant. I can only help with questions related to HDB BTO flats, eligibility rules, housing grants, and project recommendations."
    3. Application Rates & Data: Use the LATEST HDB BTO APPLICATION RATES & WEBPAGE DATA to answer any questions regarding town application rates, 2-Room/3-Room/4-Room/5-Room demand, and project details.
    4. Recommendations: If the user asks for flat choices or trade-offs, refer to the Computed BTO Recommendations above.
    5. Do not output generic static summaries if the user asked a specific question.
    """
    
    try:
        response = llm.invoke(prompt)
        explanation_content = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        print(f"[Error] LLM invocation failed: {e}")
        explanation_content = f"I encountered an error generating the response ({e}). Please try asking your question again."

    return {
        "explanation": explanation_content,
        "policy_context": policy_context
    }

# Initialize Production Graph
workflow = StateGraph(BTOState)

workflow.add_node("profile_validation", profile_validation)
workflow.add_node("load_projects", load_projects)
workflow.add_node("filter_projects", filter_projects)
workflow.add_node("rank_projects", rank_projects)
workflow.add_node("generate_explanation", generate_explanation)

workflow.set_entry_point("profile_validation")
workflow.add_edge("profile_validation", "load_projects")
workflow.add_edge("load_projects", "filter_projects")
workflow.add_edge("filter_projects", "rank_projects")
workflow.add_edge("rank_projects", "generate_explanation")
workflow.add_edge("generate_explanation", END)

app_graph = workflow.compile()
