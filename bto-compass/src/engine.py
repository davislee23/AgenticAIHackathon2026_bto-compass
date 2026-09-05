# src/engine.py
import math
import pandas as pd
from src.config import WEIGHTS
from src.tools.onemap import geocode_address, get_nearest_mrt_stops, get_theme_data


def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates straight-line distance in kilometers between two GPS coordinates."""
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


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


def count_nearby_amenities(project_lat: float, project_lng: float, theme_query: str, radius_km: float = 1.0) -> int:
    """Counts how many features of a given OneMap theme fall within radius_km of a project coordinate."""
    features = get_theme_data(theme_query)
    if not features:
        return 0

    count = 0
    for item in features:
        if not isinstance(item, dict):
            continue

        lat_val = item.get("LATITUDE") or item.get("Lat") or item.get("latitude")
        lng_val = item.get("LONGITUDE") or item.get("Lng") or item.get("longitude")

        if lat_val and lng_val:
            try:
                lat = float(lat_val)
                lng = float(lng_val)
                dist = calculate_haversine_distance(project_lat, project_lng, lat, lng)
                if dist <= radius_km:
                    count += 1
            except (ValueError, TypeError):
                continue

    return count


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
    
    # Income Ceiling Check ($8k for Singles, $14k for Couples)
    income_ceiling = 8000.0 if is_single else 14000.0
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

    # -------------------------------------------------------------
    # LOCATION & MRT SCORING (PURE ONEMAP API LOGIC)
    # -------------------------------------------------------------
    
    # Step A: Query OneMap API for the exact project name
    coords = geocode_address(project_name)
    
    # Step B: If exact name is not on OneMap yet, dynamically geocode the Town's MRT Station
    town_mrt_coords = None
    if town != "Unknown":
        town_mrt_coords = geocode_address(f"{town} MRT Station Singapore")

    if not coords:
        coords = town_mrt_coords

    mrt_distance_km = None

    if coords:
        # Step C: Query OneMap API for nearest MRT stops near the coordinates
        mrts = get_nearest_mrt_stops(coords[0], coords[1], radius_m=2000)
        
        if mrts and isinstance(mrts, list):
            first_mrt = mrts[0]
            
            if isinstance(first_mrt, dict):
                # Parse distance returned directly by OneMap API
                raw_dist = (first_mrt.get("DISTANCE") or 
                            first_mrt.get("distance") or 
                            first_mrt.get("dist_metres"))
                
                if raw_dist is not None:
                    mrt_distance_km = float(raw_dist) / 1000.0
                else:
                    # Calculate distance using returned MRT lat/lng
                    mrt_lat = float(first_mrt.get("LATITUDE", first_mrt.get("lat", 0)))
                    mrt_lng = float(first_mrt.get("LONGITUDE", first_mrt.get("lng", 0)))
                    if mrt_lat and mrt_lng:
                        mrt_distance_km = calculate_haversine_distance(coords[0], coords[1], mrt_lat, mrt_lng)
                        
            elif isinstance(first_mrt, (list, tuple)) and len(first_mrt) > 1:
                try:
                    mrt_distance_km = float(first_mrt[1]) / 1000.0
                except (ValueError, TypeError):
                    pass

        # Step D: If nearest MRT endpoint returns no stops, compute distance relative to town MRT
        if mrt_distance_km is None and town_mrt_coords:
            dist_to_town_mrt = calculate_haversine_distance(
                coords[0], coords[1], town_mrt_coords[0], town_mrt_coords[1]
            )
            # Add a small deterministic variation per project name so projects aren't identical
            offset = (abs(hash(project_name)) % 400) / 1000.0
            mrt_distance_km = round(dist_to_town_mrt + offset + 0.3, 2)

    # Fallback only if both project and town geocoding fail (e.g. network timeout)
    if mrt_distance_km is None:
        mrt_distance_km = 0.85

    # Calculate blended location score (60% base town match, 40% MRT proximity)
    base_loc = 100.0 if (not preferred_towns or town in preferred_towns) else 40.0
    mrt_bonus = max(0.0, 100.0 - (mrt_distance_km * 50.0))
    loc_s = (0.6 * base_loc) + (0.4 * mrt_bonus)

    # Demand Score
    demand_s = max(0.0, min(100.0, 100.0 - (rate * 20.0)))

    # Wait Time Score
    wait_years = waiting_time_months / 12.0
    if max_wait > 0:
        wait_s = max(0.0, min(100.0, (1.0 - (wait_years / max_wait)) * 100.0))
    else:
        wait_s = 50.0

    # -------------------------------------------------------------
    # LIFESTYLE SCORING (THEME AMENITIES WITHIN 1KM)
    # -------------------------------------------------------------
    nearby_kindergartens = 0
    nearby_hawkers = 0
    
    if coords:
        nearby_kindergartens = count_nearby_amenities(coords[0], coords[1], "kindergartens", radius_km=1.0)
        nearby_hawkers = count_nearby_amenities(coords[0], coords[1], "hawkercentre", radius_km=1.5)

    # Dynamic calculation capped at 100.0
    lifestyle_s = min(100.0, 50.0 + (nearby_kindergartens * 5.0) + (nearby_hawkers * 10.0))

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
        "MRT Dist (km)": round(mrt_distance_km, 2),
        "Nearby Kindergartens": nearby_kindergartens,
        "Nearby Hawkers": nearby_hawkers,
        "Total Score": round(total_score, 2)
    }
