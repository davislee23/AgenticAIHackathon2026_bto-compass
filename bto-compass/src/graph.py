import json
import pandas as pd
from groq import Groq
from langgraph.graph import StateGraph, END

from src.state import BTOState
from src.engine import score_project
from src.config import DATA_PATH_CSV, DATA_PATH_JSON, GROQ_MODEL
from src.rag.rag_retriever import retrieve_policy

# Initialize client once
groq_client = Groq()

def profile_validation(state: BTOState):
    print("[Node] profile_validation: Checking applicant constraints...")
    return {}

def load_projects(state: BTOState):
    print("[Node] load_projects: Loading CSV and application rates JSON...")
    df = pd.read_csv(DATA_PATH_CSV)
    
    with open(DATA_PATH_JSON, "r") as f:
        data = json.load(f)
        
    rates_dict = {}
    for row in data:
        projects_str = row.get("projects_in_group")
        rate = row.get("application_rate")
        if projects_str and pd.notna(rate):
            for name in str(projects_str).split(";"):
                rates_dict[name.strip()] = float(rate)
                
    return {
        "projects": df.to_dict(orient="records"), 
        "application_rates": rates_dict
    }

def filter_projects(state: BTOState):
    print("[Node] filter_projects: Applying budget and wait time limits...")
    applicant = state["applicant"]
    df = pd.DataFrame(state["projects"])
    
    budget_filtered = df[df["price_max_sgd"] <= applicant["budget"]]
    eligible = budget_filtered[(budget_filtered["waiting_time_months"] / 12.0) <= applicant["max_wait"]]
    
    return {"eligible_projects": eligible.to_dict(orient="records")}

def rank_projects(state: BTOState):
    print("[Node] rank_projects: Computing deterministic scores...")
    applicant = state["applicant"]
    df = pd.DataFrame(state["eligible_projects"])
    rates = state["application_rates"]
    
    scores = [
        score_project(row, rates.get(row["project_name"], 2.0), applicant)
        for _, row in df.iterrows()
    ]
    
    ranked_df = pd.DataFrame(scores).sort_values(by="Total Score", ascending=False).head(3)
    return {"rankings": ranked_df.to_dict(orient="records")}

def generate_explanation(state: BTOState):
    print("[Node] generate_explanation: Retrieving context and prompting LLM...")
    applicant = state["applicant"]
    
    if not state.get("rankings"):
        return {"explanation": "No projects match your constraints."}
        
    rankings_str = pd.DataFrame(state["rankings"]).to_string(index=False)
    
    # Retrieve relevant policy rules
    query = f"HDB BTO application rules for {applicant.get('applicant_type', 'single')} applicants"
    policy_context = retrieve_policy(query, top_k=1)
    
    prompt = f"""
    You are an expert Singapore housing advisor.
    Applicant Constraints: Type: {applicant.get('applicant_type', 'single')}, Budget SGD {applicant['budget']}, Max Wait {applicant['max_wait']} years.
    
    Deterministic Ranked Top 3 BTO Recommendations:
    {rankings_str}
    
    HDB Policy Reference:
    {policy_context}
    
    Instructions:
    1. Explain why Rank #1 ranks highest for this applicant.
    2. Describe the trade-offs between the Top 3.
    3. Flag 1-2 eligibility points strictly referencing the policy above.
    4. NEVER recalculate or override the deterministic ranking.
    """
    
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return {"explanation": response.choices[0].message.content}
    
# Initialize Production Graph (No simulation loops)
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
