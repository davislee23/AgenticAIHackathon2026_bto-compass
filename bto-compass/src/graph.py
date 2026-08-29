import os
import json
import pandas as pd
from dotenv import load_dotenv
from groq import Groq
from langgraph.graph import StateGraph, START, END
from src.state import BTOState

# ==========================================
# 1. NODE FUNCTIONS
# ==========================================

def profile_validation(state: BTOState):
    print("[Node] profile_validation: Checking applicant constraints...")
    return {"iteration_count": state.get("iteration_count", 0) + 1}

def load_projects(state: BTOState):
    print("[Node] load_projects: Loading CSV and application rates JSON...")
    
    # Load project dataframe
    df = pd.read_csv("data/bto_flat_offerings_feb2026.csv")
    
    # Load application rates JSON and parse into a dictionary lookup
    with open("data/application_rates/application_rates_feb2026.json", "r") as f:
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
    
    # Hard constraints filtering
    budget_filtered = df[df["price_max_sgd"] <= applicant["budget"]]
    eligible = budget_filtered[(budget_filtered["waiting_time_months"] / 12.0) <= applicant["max_wait"]]
    
    return {"eligible_projects": eligible.to_dict(orient="records")}

def rank_projects(state: BTOState):
    print("[Node] rank_projects: Computing deterministic scores and sorting Top 3...")
    applicant = state["applicant"]
    df = pd.DataFrame(state["eligible_projects"])
    rates = state["application_rates"]
    
    scores = []
    for _, row in df.iterrows():
        proj_name = row["project_name"]
        rate = rates.get(proj_name, 2.0)
        
        # Scoring metrics (0 to 100)
        afford_s = max(0.0, min(100.0, ((applicant["budget"] - row["price_max_sgd"]) / applicant["budget"]) * 100))
        loc_s = 100.0 if row["town"] in applicant["preferred_towns"] else 50.0
        demand_s = max(0.0, min(100.0, 100.0 - (rate * 20.0)))
        
        wait_years = row["waiting_time_months"] / 12.0
        wait_s = max(0.0, (1.0 - (wait_years / applicant["max_wait"])) * 100)
        lifestyle_s = 80.0  # Static baseline
        
        # Weighted formula: 30% affordability + 25% location + 20% demand + 15% wait + 10% lifestyle
        total_score = (
            0.30 * afford_s +
            0.25 * loc_s +
            0.20 * demand_s +
            0.15 * wait_s +
            0.10 * lifestyle_s
        )
        
        scores.append({
            "Project": proj_name,
            "Town": row["town"],
            "Max Price": row["price_max_sgd"],
            "Wait (Yrs)": round(wait_years, 1),
            "Demand Rate": rate,
            "Total Score": round(total_score, 2)
        })
    
    ranked_df = pd.DataFrame(scores).sort_values(by="Total Score", ascending=False).head(3)
    return {"rankings": ranked_df.to_dict(orient="records")}

def generate_explanation(state: BTOState):
    print("[Node] generate_explanation: Asking Groq to interpret the Top 3...\n")
    load_dotenv()
    client = Groq()
    model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    
    rankings_str = pd.DataFrame(state["rankings"]).to_string(index=False)
    
    prompt = f"""
    You are an expert Singapore housing advisor.
    Applicant Constraints: Budget ${state["applicant"]["budget"]}, Max Wait {state["applicant"]["max_wait"]} years.
    
    Deterministic Ranked Top 3 BTO Recommendations:
    {rankings_str}
    
    Instructions:
    1. Explain why Rank #1 ranks highest.
    2. Describe the trade-offs between the Top 3.
    3. Flag 1-2 eligibility or financing points the applicant should verify.
    4. NEVER recalculate or override the deterministic ranking.
    """
    
    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return {"explanation": response.choices[0].message.content}

# ==========================================
# 2. COMPILE THE GRAPH
# ==========================================
builder = StateGraph(BTOState)

# Add nodes
builder.add_node("profile_validation", profile_validation)
builder.add_node("load_projects", load_projects)
builder.add_node("filter_projects", filter_projects)
builder.add_node("rank_projects", rank_projects)
builder.add_node("generate_explanation", generate_explanation)

# Wire the edges together sequentially
builder.add_edge(START, "profile_validation")
builder.add_edge("profile_validation", "load_projects")
builder.add_edge("load_projects", "filter_projects")
builder.add_edge("filter_projects", "rank_projects")
builder.add_edge("rank_projects", "generate_explanation")
builder.add_edge("generate_explanation", END)

# Export the compiled graph app
app_graph = builder.compile()
