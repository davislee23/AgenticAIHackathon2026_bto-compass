import pandas as pd
import json
from src.graph import app_graph
# ==========================================
# 1. LOAD FUNCTIONS
# ==========================================
def load_projects(csv_path="data/bto_flat_offerings_feb2026.csv") -> pd.DataFrame:
    """Read project data from CSV."""
    return pd.read_csv(csv_path)

def load_application_rates(json_path: str) -> dict:
    """Load application demand snapshot and convert it to a lookup dictionary."""
    with open(json_path, "r") as f:
        data = json.load(f)
        
    rates_dict = {}
    for row in data:
        projects_str = row.get("projects_in_group")
        rate = row.get("application_rate")
        
        # Parse valid rates and split grouped projects (e.g. "Sembawang Voyage;Sembawang Deck")
        if projects_str and pd.notna(rate):
            project_names = str(projects_str).split(";")
            for name in project_names:
                rates_dict[name.strip()] = float(rate)
                
    return rates_dict

# ==========================================
# 2. FILTER FUNCTIONS
# ==========================================
def filter_by_budget(df: pd.DataFrame, max_budget: float) -> pd.DataFrame:
    """Remove projects where the maximum estimated price is above the applicant budget."""
    return df[df["price_max_sgd"] <= max_budget].copy()

def filter_by_waiting_time(df: pd.DataFrame, max_wait_years: float) -> pd.DataFrame:
    """Remove projects beyond the acceptable wait (converting months to years)."""
    return df[(df["waiting_time_months"] / 12.0) <= max_wait_years].copy()

# ==========================================
# 3. SCORING FUNCTIONS
# ==========================================
def demand_score(rate: float) -> float:
    """Convert application rate into a transparent demand score."""
    return max(0.0, min(100.0, 100.0 - (rate * 20.0)))

def affordability_score(price: float, budget: float) -> float:
    """Score the amount of budget headroom."""
    headroom = (budget - price) / budget
    return max(0.0, min(100.0, headroom * 100.0))

# ==========================================
# 4. RANKING ENGINE
# ==========================================
def calculate_rankings(df: pd.DataFrame, demand_rates: dict, applicant: dict) -> pd.DataFrame:
    """Combine weighted scores and sort projects."""
    scores = []
    
    for _, row in df.iterrows():
        # Change: Look up by project_name, not project_id
        proj_name = row["project_name"]
        rate = demand_rates.get(proj_name, 2.0)
        
        # Calculate individual metrics
        afford_s = affordability_score(row["price_max_sgd"], applicant["budget"])
        loc_s = 100.0 if row["town"] in applicant["preferred_towns"] else 50.0
        demand_s = demand_score(rate)
        
        # Convert months to years for the wait score formula
        wait_years = row["waiting_time_months"] / 12.0
        wait_s = max(0.0, (1.0 - (wait_years / applicant["max_wait"])) * 100)
        
        lifestyle_s = 80.0  # Assumed static baseline for MVP
        
        # Apply the exact guide weights
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
    
    # Sort by highest score first
    ranked_df = pd.DataFrame(scores).sort_values(by="Total Score", ascending=False).reset_index(drop=True)
    return ranked_df

# ==========================================
# 5. DEFINITION OF DONE VERIFICATION
# ==========================================
if __name__ == "__main__":
    # Define the applicant profile
    initial_state = {
        "applicant": {
            "budget": 450000,
            "max_wait": 4.0,
            "preferred_towns": ["Woodlands", "Tampines", "Sengkang"]
        },
        "data_changed": False,
        "iteration_count": 0
    }
    
    print("==================================================")
    print("        RUNNING BTO COMPASS LANGGRAPH MVP         ")
    print("==================================================")
    
    # Invoke the compiled LangGraph pipeline
    final_state = app_graph.invoke(initial_state)
    
    print("\n==================================================")
    print("               FINAL LLM EXPLANATION              ")
    print("==================================================")
    print(final_state["explanation"])
    
    print(f"--- Applicant Profile ---")
    print(f"Budget: SGD {applicant_profile['budget']}")
    print(f"Max Wait: {applicant_profile['max_wait']} years\n")
    
    # Load and filter
    raw_df = load_projects()
    budget_filtered = filter_by_budget(raw_df, applicant_profile["budget"])
    eligible_df = filter_by_waiting_time(budget_filtered, applicant_profile["max_wait"])
    print(f"[✓] Eligible Projects after filters: {len(eligible_df)}\n")
    
    # Test Day 1
    try:
        # Note: Ensure this path matches exactly where your JSON file is!
        day1_rates = load_application_rates("data/application_rates/application_rates_feb2026.json")
        top3_day1 = calculate_rankings(eligible_df, day1_rates, applicant_profile).head(3)
        print("--- TOP 3: DAY 1 DEMAND ---")
        print(top3_day1.to_string(index=False))
    except FileNotFoundError:
        print("[!] Warning: JSON not found. Please verify the file path.")
