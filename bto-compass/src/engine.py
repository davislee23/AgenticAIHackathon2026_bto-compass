# src/engine.py
import pandas as pd
from src.config import WEIGHTS

def score_project(row: pd.Series, rate: float, applicant: dict) -> dict:
    # Safely extract applicant constraints with fallbacks
    budget = applicant.get("budget", 500000.0)
    preferred_towns = applicant.get("preferred_towns", [])
    max_wait = applicant.get("max_wait", 5.0)

    # Safely extract row properties with fallbacks
    price_max_sgd = row.get("price_max_sgd", 0.0)
    town = row.get("town", "Unknown")
    project_name = row.get("project_name", "Unknown Project")
    waiting_time_months = row.get("waiting_time_months", 36.0)

    # 1. Affordability Score (Safeguard against division by zero)
    if budget > 0:
        afford_s = max(0.0, min(100.0, ((budget - price_max_sgd) / budget) * 100))
    else:
        afford_s = 50.0

    # 2. Location Score
    loc_s = 100.0 if town in preferred_towns else 50.0

    # 3. Demand Score
    demand_s = max(0.0, min(100.0, 100.0 - (rate * 20.0)))

    # 4. Wait Time Score (Safeguard against division by zero)
    wait_years = waiting_time_months / 12.0
    if max_wait > 0:
        wait_s = max(0.0, (1.0 - (wait_years / max_wait)) * 100)
    else:
        wait_s = 50.0

    # 5. Lifestyle Score
    lifestyle_s = 80.0

    # Weighted Total Calculation
    total_score = (
        WEIGHTS.get("affordability", 0.30) * afford_s +
        WEIGHTS.get("location", 0.25) * loc_s +
        WEIGHTS.get("demand", 0.20) * demand_s +
        WEIGHTS.get("wait", 0.15) * wait_s +
        WEIGHTS.get("lifestyle", 0.10) * lifestyle_s
    )

    return {
        "project_name": project_name,
        "Project": project_name,
        "Town": town,
        "Max Price": price_max_sgd,
        "Wait (Yrs)": round(wait_years, 1),
        "Demand Rate": rate,
        "Total Score": round(total_score, 2)
    }
