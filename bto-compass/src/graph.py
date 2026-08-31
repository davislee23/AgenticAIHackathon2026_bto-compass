import json
import pandas as pd
from langgraph.graph import StateGraph, END

from src.state import BTOState
from src.engine import score_project
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

def profile_validation(state: BTOState):
    print("[Node] profile_validation: Checking applicant constraints...")
    return {}

ddef load_projects(state: BTOState):
    print("[Node] load_projects: Loading dataset...")
    
    csv_path = Path(DATA_PATH_CSV)
    json_path = Path(DATA_PATH_JSON)

    # Fallback to parent directory if data subfolder is placed in repo root
    if not csv_path.exists():
        alt_csv = Path(__file__).resolve().parent.parent.parent / "data" / "bto_projects.csv"
        if alt_csv.exists():
            csv_path = alt_csv

    if not json_path.exists():
        alt_json = Path(__file__).resolve().parent.parent.parent / "data" / "application_rates.json"
        if alt_json.exists():
            json_path = alt_json

    # Load CSV
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"[Error] Failed reading CSV at {csv_path}: {e}")
        df = pd.DataFrame()

    # Load JSON rates
    rates_dict = {}
    if json_path.exists():
        try:
            with open(json_path, "r") as f:
                json_data = json.load(f)
            for row in json_data:
                projects_str = row.get("projects_in_group")
                rate = row.get("application_rate")
                if projects_str and pd.notna(rate):
                    for name in str(projects_str).split(";"):
                        rates_dict[name.strip()] = float(rate)
        except Exception as e:
            print(f"[Warning] Could not load application rates JSON: {e}")

    return {
        "projects": df.to_dict(orient="records"),
        "application_rates": rates_dict
    }

# In src/graph.py

def filter_projects(state: BTOState):
    print("[Node] filter_projects: Applying budget and wait time limits...")
    applicant = state.get("applicant") or {}
    
    # Coerce to numbers with fallbacks
    budget = applicant.get("budget")
    if budget is None or budget <= 0:
        budget = 2000000.0  # Default to open budget if unset
        
    max_wait = applicant.get("max_wait")
    if max_wait is None or max_wait <= 0:
        max_wait = 10.0      # Default to max wait if unset
    
    df = pd.DataFrame(state.get("projects", []))
    if df.empty:
        return {"eligible_projects": []}
    
    budget_filtered = df[df["price_max_sgd"] <= budget]

    if "waiting_time_months" in budget_filtered.columns:
        eligible = budget_filtered[(budget_filtered["waiting_time_months"] / 12.0) <= max_wait]
    else:
        eligible = budget_filtered
    
    return {"eligible_projects": eligible.to_dict(orient="records")}

def rank_projects(state: BTOState):
    print("[Node] rank_projects: Computing deterministic scores...")
    applicant = state.get("applicant") or {}
    eligible_projects = state.get("eligible_projects", [])
    
    if not eligible_projects:
        return {"rankings": []}
        
    df = pd.DataFrame(eligible_projects)
    rates = state.get("application_rates", {})
    
    scores = [
        score_project(row, rates.get(row.get("project_name"), 2.0), applicant)
        for _, row in df.iterrows()
    ]
    
    ranked_df = pd.DataFrame(scores).sort_values(by="Total Score", ascending=False).head(3)
    return {"rankings": ranked_df.to_dict(orient="records")}

# src/graph.py

# In src/graph.py

def generate_explanation(state: BTOState):
    print("[Node] generate_explanation: Retrieving context and prompting LLM...")
    applicant = state.get("applicant") or {}
    rankings = state.get("rankings", [])
    messages = state.get("messages", [])
    
    # Robustly extract user query text across different message types
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
    
    # Retrieve policy context tailored directly to user query
    policy_context = retrieve_policy(user_query, top_k=2)
    
    prompt = f"""
    You are an expert Singapore housing advisor specialized in Singapore HDB housing, BTO flats, CPF grants, and eligibility assisting an applicant.

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

    HDB POLICY REFERENCE:
    {policy_context}

    INSTRUCTIONS:
    1. Direct Answer: Answer the USER'S QUESTION directly in sentence
    2. STRICT DOMAIN GUARDRAIL: Check if the user's question is related to Singapore housing, HDB/BTO flats, CPF grants, home buying, or applicant eligibility. 
       - If the query is OUT OF SCOPE (e.g., cooking, programming, general trivia, stock advice, unrelated topics), politely refuse: "I am BTO Compass, a specialized Singapore housing assistant. I can only help with questions related to HDB BTO flats, eligibility rules, housing grants, and project recommendations."
    3. Contextual Focus: If the user asks about grants, eligibility, or rules, focus primarily on explaining that topic using the HDB Policy Reference.
    4. Recommendations: If the user asks for flat choices or trade-offs, refer to the Computed BTO Recommendations above.
    5. Do not output generic static summaries if the user asked a specific question.
    """
    
# 4. Safeguard LLM call against timeout/crash
    try:
        response = llm.invoke(prompt)
        explanation_content = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        print(f"[Error] LLM invocation failed: {e}")
        explanation_content = f"I encountered an error generating the response ({e}). Please try asking your question again."

    return {"explanation": explanation_content}
    
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
