# src/tools/tools.py
from langchain_core.tools import tool
from src.rag.rag_retriever import retrieve_policy
from src.engine import calculate_ehg_grant
from src.tools.onemap import geocode_address, find_nearby_amenities

@tool
def search_hdb_policies(query: str) -> str:
    """Searches official HDB eligibility rules and housing policy documentation."""
    return retrieve_policy(query)
    
@tool
def get_project_amenities(location_name: str) -> str:
    """Finds coordinates and nearby MRTs, Bus Stops, Hawkers, and Schools for a BTO project."""
    coords = geocode_address(location_name)
    if not coords:
        return f"Location '{location_name}' not found on OneMap."
    
    lat, lng = coords
    amenities = find_nearby_amenities(lat, lng, radius_km=1.2)
    
    mrt_list = ", ".join([f"{m['name']} ({m['distance_km']}km)" for m in amenities["mrt"][:3]]) or "None within 1.2km"
    bus_list = ", ".join([f"{b['name']} ({b['distance_km']}km)" for b in amenities["bus_stops"][:3]]) or "None within 1.2km"
    hawker_list = ", ".join([f"{h['name']} ({h['distance_km']}km)" for h in amenities["hawker"][:2]]) or "None within 1.2km"
    school_list = ", ".join([f"{s['name']} ({s['distance_km']}km)" for s in amenities["school"][:2]]) or "None within 1.2km"

    return (
        f"**Amenities for {location_name}**:\n"
        f"- MRT/LRT: {mrt_list}\n"
        f"- Bus Stops: {bus_list}\n"
        f"- Food/Hawker: {hawker_list}\n"
        f"- Schools: {school_list}"
    )   
