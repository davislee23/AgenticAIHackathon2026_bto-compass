# src/engine.py
import pandas as pd
from src.config import WEIGHTS

def calculate_ehg_grant(monthly_income: float, is_single: bool = False) -> float:
    """Calculates Enhanced CPF Housing Grant (EHG) tier based on monthly income."""
    ceiling = 4500.0 if is_single else 9000.0
    if monthly_income <= 0 or monthly_income > ceiling:
        return 0.0
    
    max_grant = 40000.0 if is_single else 80000.0
    step = 2500.0 if is_single else 5000.0
    base_income = 750.0 if is_single else 1500.0
    
    if monthly_income <= base_income:
        return max_grant
        
    bracket = int((monthly_income - base_income - 1) // 500) + 1
    grant = max_grant - (bracket * step)
    return max(0.0, grant)


def score_project(row: pd.Series, rate: float, applicant: dict) -> dict:
    # 1. Extract Applicant Profile
    raw_budget = float(applicant.get("budget", 500000.0))
    income = float(applicant.get("monthly_income", 0.0))
    applicant_type = str(applicant.get("applicant_type", "Couple")).strip().title()
    is_single = (applicant_type == "Single")
    
    preferred_towns = applicant.get("preferred_towns", [])
    max_wait = float(applicant.get("max_wait", 5.0))

    # 2. Extract Project Properties
    price_min = float(row.get("price_min_sgd", row.get("price_max_sgd", 0.0)))
    price_max = float(row.get("price_max_sgd", price_min))
    town = str(row.get("town", "Unknown"))
    project_name = str(row.get("project_name", "Unknown Project"))
    flat_type = str(row.get("flat_type", "")).lower()
    waiting_time_months = float(row.get("waiting_time_months", 36.0))
    classification = str(row.get("classification", "Standard"))

    # -------------------------------------------------------------
    # HARD ELIGIBILITY FILTERS (Returns None if Ineligible)
    # -------------------------------------------------------------
    
    # Income Ceiling Check ($7k for Singles, $14k for Couples)
    income_ceiling = 7000.0 if is_single else 14000.0
    if income > income_ceiling:
        return None

    # Single Flat Type Constraint (Singles 35+ restricted to 2-Room Flexi)
    if is_single and "2-room" not in flat_type and "2 room" not in flat_type:
        return None

    # Budget & Grant Hard Limit
    grant = calculate_ehg_grant(income, is_single=is_single)
    effective_budget = raw_budget + grant

    if price_min > effective_budget:
        return None

    # -------------------------------------------------------------
    # SOFT SCORING (For eligible projects)
    # -------------------------------------------------------------
    
    # Affordability Score
    if effective_budget > 0:
        price_delta = effective_budget - price_max
        afford_s = max(0.0, min(100.0, 50.0 + (price_delta / effective_budget) * 50.0))
    else:
        afford_s = 50.0

    # Location Score
    loc_s = 100.0 if (not preferred_towns or town in preferred_towns) else 40.0

    # Demand Score
    demand_s = max(0.0, min(100.0, 100.0 - (rate * 20.0)))

    # Wait Time Score
    wait_years = waiting_time_months / 12.0
    if max_wait > 0:
        wait_s = max(0.0, min(100.0, (1.0 - (wait_years / max_wait)) * 100.0))
    else:
        wait_s = 50.0

    # Lifestyle Score
    lifestyle_s = 80.0

    # Weighted Total Score
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
        "Flat Type": row.get("flat_type", "N/A"),
        "Classification": classification,
        "Min Price": price_min,
        "Max Price": price_max,
        "EHG Grant": grant,
        "Wait (Yrs)": round(wait_years, 1),
        "Demand Rate": rate,
        "Total Score": round(total_score, 2)
    }
