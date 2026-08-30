import json
import pandas as pd
from groq import Groq
from langgraph.graph import StateGraph, START, END

from src.state import BTOState
from src.engine import score_project
from src.config import DATA_PATH_CSV, DATA_PATH_JSON, GROQ_MODEL

from src.rag.rag_retriever import retrieve_policy

# Initialize client once to eliminate overhead during graph execution
groq_client = Groq()

def profile_validation(state: BTOState):
    print("[Node] profile_validation: Checking applicant constraints...")
    # Remove iteration incrementing from here so iteration tracking starts clean
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
    print("[Node] rank_projects: Computing deterministic scores and sorting Top 3...")
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
    applicant = state["applicant"]
    rankings_str = pd.DataFrame(state["rankings"]).to_string(index=False)
    
    # Retrieve relevant policy rules for singles
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
    1. Explain why Rank #1 ranks highest for this single applicant.
    2. Describe the trade-offs between the Top 3.
    3. Flag 1-2 eligibility points (e.g., 2-room Flexi restrictions or income ceilings for singles) strictly referencing the policy above.
    4. NEVER recalculate or override the deterministic ranking.
    """
    
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return {"explanation": response.choices[0].message.content}
    
def simulate_user_feedback(state: BTOState):
    """Simulates the user deciding to increase their budget after seeing the first results."""
    iteration = state.get("iteration_count", 0)
    
    if iteration == 0:
        print("\n--- [SIMULATION] User increased budget to $350,000 ---")
        # Create an updated copy of the applicant profile
        new_applicant = dict(state["applicant"])
        new_applicant["budget"] = 350000
        
        # Explicitly return updated applicant and set iteration_count to 1
        return {
            "applicant": new_applicant, 
            "iteration_count": 1
        }
        
    return {"iteration_count": iteration + 1}

def should_replan(state: BTOState):
    """Router function to determine if we need to loop back."""
    # Replan when iteration_count is 1 (right after the budget update)
    if state.get("iteration_count", 0) == 1:
        return "replan"
    return "end"
    
# Initialize Graph
workflow = StateGraph(BTOState)

# 1. Add All Nodes
workflow.add_node("profile_validation", profile_validation)
workflow.add_node("load_projects", load_projects)
workflow.add_node("filter_projects", filter_projects)
workflow.add_node("rank_projects", rank_projects)
workflow.add_node("generate_explanation", generate_explanation)
workflow.add_node("simulate_user_feedback", simulate_user_feedback)

# 2. Set Entry Point and Linear Edges
workflow.set_entry_point("profile_validation") 
workflow.add_edge("profile_validation", "load_projects")
workflow.add_edge("load_projects", "filter_projects")
workflow.add_edge("filter_projects", "rank_projects")
workflow.add_edge("rank_projects", "generate_explanation")
workflow.add_edge("generate_explanation", "simulate_user_feedback")

# 3. Add Conditional Edge for Re-planning
workflow.add_conditional_edges(
    "simulate_user_feedback",
    should_replan,
    {
        # On replan, loop back to filter_projects. 
        # This is efficient because it skips re-loading the CSV files!
        "replan": "filter_projects", 
        "end": END
    }
)

app_graph = workflow.compile()
