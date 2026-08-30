import pandas as pd
from src.config import WEIGHTS

def score_project(row: pd.Series, rate: float, applicant: dict) -> dict:
    afford_s = max(0.0, min(100.0, ((applicant["budget"] - row["price_max_sgd"]) / applicant["budget"]) * 100))
    loc_s = 100.0 if row["town"] in applicant["preferred_towns"] else 50.0
    demand_s = max(0.0, min(100.0, 100.0 - (rate * 20.0)))
    
    wait_years = row["waiting_time_months"] / 12.0
    wait_s = max(0.0, (1.0 - (wait_years / applicant["max_wait"])) * 100)
    lifestyle_s = 80.0
    
    total_score = (
        WEIGHTS["affordability"] * afford_s +
        WEIGHTS["location"] * loc_s +
        WEIGHTS["demand"] * demand_s +
        WEIGHTS["wait"] * wait_s +
        WEIGHTS["lifestyle"] * lifestyle_s
    )
    
    return {
        "Project": row["project_name"],
        "Town": row["town"],
        "Max Price": row["price_max_sgd"],
        "Wait (Yrs)": round(wait_years, 1),
        "Demand Rate": rate,
        "Total Score": round(total_score, 2)
    }
