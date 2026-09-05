# app.py
import streamlit as st
import sys
import math
import pandas as pd
import pydeck as pdk
import requests
import os
from pathlib import Path

# Add the directory containing app.py to Python's import search path
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
    
from src.tools.onemap import geocode_address
from langchain_core.messages import HumanMessage
from src.graph import app_graph
from src.cost_tracker import UsageTracker
from src.extractors import extract_income_from_pdf
from src.rag.rates_reader import get_application_rates_context
from src.llm import get_active_provider_info

# --- HELPER FUNCTIONS ---
def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates distance between two coordinates in kilometers."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def extract_lat_lon(item):
    """Safely extracts latitude and longitude from OneMap's varying JSON structures."""
    if not isinstance(item, dict): 
        return None, None
    
    # 1. Check for standard keys first
    lat = item.get("LATITUDE") or item.get("Lat") or item.get("Y_ADDR")
    lon = item.get("LONGITUDE") or item.get("Lng") or item.get("X_ADDR")
    
    # 2. Check for the single "LatLng" string (used by Kindergartens and Hawkers)
    # Format: "1.279313936, 103.8466601"
    if not lat and not lon and item.get("LatLng"):
        parts = str(item.get("LatLng")).split(",")
        if len(parts) >= 2:
            lat = parts[0].strip()
            lon = parts[1].strip()
            
    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None, None

@st.cache_data(ttl=3600)
def fetch_cached_amenities():
    """Fetches OneMap theme data with Authentication headers."""
    kindergartens = []
    hawkers = []
    
    # IMPORTANT: Grab your token from your environment variables
    # (Ensure you have ONEMAP_TOKEN set in your .env file)
    token = os.environ.get("ONEMAP_TOKEN", "")
    
    headers = {
        "Authorization": f"Bearer {token}" if token else "",
        "User-Agent": "Mozilla/5.0"
    }
    
    # 1. Fetch Kindergartens
    try:
        url_k = "https://www.onemap.gov.sg/api/public/themesvc/retrieveTheme?queryName=kindergartens"
        resp_k = requests.get(url_k, headers=headers, timeout=10)
        if resp_k.status_code == 200:
            data = resp_k.json()
            if "SrchResults" in data:
                # Slice [1:] to skip the FeatCount metadata dictionary
                kindergartens = [item for item in data["SrchResults"][1:] if extract_lat_lon(item)[0]]
    except Exception as e:
        print(f"Kindergarten Fetch Error: {e}")

    # 2. Fetch Hawker Centres
    try:
        url_h = "https://www.onemap.gov.sg/api/public/themesvc/retrieveTheme?queryName=hawkercentre"
        resp_h = requests.get(url_h, headers=headers, timeout=10)
        if resp_h.status_code == 200:
            data = resp_h.json()
            if "SrchResults" in data:
                # Slice [1:] to skip the FeatCount metadata dictionary
                hawkers = [item for item in data["SrchResults"][1:] if extract_lat_lon(item)[0]]
    except Exception as e:
        print(f"Hawker Fetch Error: {e}")
        
    return kindergartens, hawkers

# --- MAIN APP ---
st.set_page_config(page_title="BTO Compass", layout="wide")
st.title("🏡 BTO Compass AI Assistant")

tracker = UsageTracker()

# Safe default session state initialization dictionary
DEFAULTS = {
    "monthly_income": 0.0,
    "budget": 500000.0,
    "is_first_timer": True,
    "preferred_towns": [],
    "max_wait": 5.0,
    "applicant_type": "couple",
    "messages": [],
    "last_graph_response": None  
}

for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val
        
provider_info = get_active_provider_info()

with st.sidebar:
    st.subheader("LLM Backend Status")
    st.caption(f"{provider_info['icon']} **Provider:** {provider_info['provider']}")
    st.caption(f"🤖 **Model:** `{provider_info['model']}`")
    st.divider()
    
# Sidebar Controls & Document Uploader
with st.sidebar:
    st.header("📄 Payslip Auto-Fill")
    uploaded_pdf = st.file_uploader("Upload Payslip (PDF)", type=["pdf"])
    if uploaded_pdf and st.button("Extract Income"):
        pdf_bytes = uploaded_pdf.read()
        try:
            extracted = extract_income_from_pdf(pdf_bytes)
            st.session_state["monthly_income"] = float(extracted.gross_income)
            st.success(f"Extracted Income: ${extracted.gross_income:,.2f} SGD")
        except Exception as e:
            st.error(f"Error extracting income: {e}")

    st.divider()
    st.header("👤 Applicant Profile")
    
    monthly_income = st.number_input("Gross Monthly Household Income (SGD)", min_value=0.0, value=float(st.session_state["monthly_income"]), step=500.0)
    st.session_state["monthly_income"] = monthly_income

    budget = st.number_input("Max Housing Budget (SGD)", min_value=100000.0, max_value=2000000.0, value=float(st.session_state["budget"]), step=25000.0)
    st.session_state["budget"] = budget

    preferred_towns = st.multiselect("Preferred Towns", options=["Yishun", "Kallang / Whampoa", "Bishan", "Tampines", "Punggol", "Jurong East", "Woodlands", "Bedok"], default=st.session_state["preferred_towns"])
    st.session_state["preferred_towns"] = preferred_towns

    max_wait = st.slider("Max Waiting Time (Years)", min_value=1.0, max_value=10.0, value=float(st.session_state["max_wait"]), step=0.5)
    st.session_state["max_wait"] = max_wait

    applicant_type_label = st.selectbox("Applicant Type", options=["Couple / Family", "Single (35+)"], index=0 if st.session_state["applicant_type"] == "couple" else 1)
    st.session_state["applicant_type"] = "couple" if applicant_type_label == "Couple / Family" else "single"

    is_first_timer = st.checkbox("First-Time BTO Applicant", value=st.session_state["is_first_timer"])
    st.session_state["is_first_timer"] = is_first_timer

# Display Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ==========================================
# 1. CHAT INPUT BLOCK
# ==========================================
if prompt := st.chat_input("Ask about BTO eligibility, housing grants, or flat recommendations..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        applicant_data = {
            "monthly_income": float(st.session_state.get("monthly_income") or 0.0),
            "is_first_timer": bool(st.session_state.get("is_first_timer", True)),
            "budget": float(st.session_state.get("budget") or 500000.0),
            "preferred_towns": st.session_state.get("preferred_towns") or [],
            "max_wait": float(st.session_state.get("max_wait") or 5.0),
            "applicant_type": str(st.session_state.get("applicant_type") or "couple")
        }

        rates_context = get_application_rates_context()

        with st.spinner("Analyzing housing options..."):
            response = app_graph.invoke({
                "messages": [HumanMessage(content=prompt)],
                "applicant": applicant_data,
                "rates_context": rates_context  
            })

        st.session_state["last_graph_response"] = response

        if isinstance(response, dict) and "explanation" in response:
            assistant_output = response["explanation"]
        elif isinstance(response, dict) and "messages" in response and response["messages"]:
            last_msg = response["messages"][-1]
            assistant_output = getattr(last_msg, "content", str(last_msg))
        else:
            assistant_output = "No recommendations found."

        st.markdown(assistant_output)
        st.session_state.messages.append({"role": "assistant", "content": assistant_output})

# ==========================================
# 2. PERSISTENT UI BLOCK (Map & Expanders)
# ==========================================
if st.session_state.get("last_graph_response"):
    response = st.session_state["last_graph_response"]
    
    raw_projects = response.get("rankings", [])
    if not raw_projects:
        raw_projects = response.get("eligible_projects", [])
    
    # FIX 1: Deduplicate projects to prevent duplicate columns
    recommended_projects = []
    seen = set()
    for p in raw_projects:
        p_name = p.get("project_name") if isinstance(p, dict) else str(p)
        if p_name not in seen:
            seen.add(p_name)
            recommended_projects.append(p)
    
    if recommended_projects:
        st.divider()
        st.subheader("📍 Recommended Locations & Amenities (1.5km Radius)")
        st.markdown("🔴 **BTO Project** | 🟠 **Hawker Centre** | 🔵 **Kindergarten**")
        
        with st.spinner("Fetching OneMap amenity data..."):
            global_kindergartens, global_hawkers = fetch_cached_amenities()
        
        cols = st.columns(min(len(recommended_projects), 3)) 
        
        # FIX 2: Inline cache to prevent API rate-limiting on repetitive searches
        geocode_cache = {}
        def get_cached_coords(search_str):
            if search_str not in geocode_cache:
                geocode_cache[search_str] = geocode_address(search_str)
            return geocode_cache[search_str]
        
        for idx, project in enumerate(recommended_projects[:3]):
            proj_name = project.get("project_name") if isinstance(project, dict) else str(project)
            
            with cols[idx]:
                st.write(f"**{proj_name}**")
                
                # --- Fallback Geocoding Strategy (Cached) ---
                coords = get_cached_coords(proj_name)
                
                # Fallback 1: Remove "BTO" or "Project" from the string
                if not coords:
                    clean_name = proj_name.replace("BTO", "").replace("Project", "").strip()
                    coords = get_cached_coords(clean_name)
                
                # Fallback 2: Just search the Town Name (usually the first word, e.g., "Yishun")
                if not coords and " " in clean_name:
                    town_name = clean_name.split()[0]
                    coords = get_cached_coords(town_name)
                # -----------------------------------
                
                if coords:
                    proj_lat, proj_lng = coords
                    map_points = []
                    
                    # Base Project Pin
                    map_points.append({
                        "name": f"Location: {proj_name}",
                        "type": "Project",
                        "lat": proj_lat,
                        "lon": proj_lng,
                        "color": [220, 38, 38, 255], 
                        "radius": 150
                    })
                    
                    # Kindergartens
                    for k in global_kindergartens:
                        lat, lng = extract_lat_lon(k)
                        if lat and lng and calculate_haversine_distance(proj_lat, proj_lng, lat, lng) <= 1.5:
                            map_points.append({
                                "name": k.get("NAME") or k.get("Name") or k.get("BUILDING_NAME") or "Kindergarten",
                                "type": "Kindergarten",
                                "lat": lat, "lon": lng,
                                "color": [59, 130, 246, 200], "radius": 70
                            })

                    # Hawkers
                    for h in global_hawkers:
                        lat, lng = extract_lat_lon(h)
                        if lat and lng and calculate_haversine_distance(proj_lat, proj_lng, lat, lng) <= 1.5:
                            map_points.append({
                                "name": h.get("NAME") or h.get("Name") or h.get("ADDRESSBUILDINGNAME") or "Hawker",
                                "type": "Hawker Centre",
                                "lat": lat, "lon": lng,
                                "color": [249, 115, 22, 200], "radius": 90
                            })
                    
                    if map_points:
                        map_df = pd.DataFrame(map_points)
                        
                        layer = pdk.Layer(
                            "ScatterplotLayer",
                            data=map_df,
                            get_position='[lon, lat]',
                            get_color='color',
                            get_radius='radius',
                            pickable=True,
                            opacity=0.8,
                            filled=True
                        )
                        
                        view_state = pdk.ViewState(latitude=proj_lat, longitude=proj_lng, zoom=13.5, pitch=0)
                        tooltip = {"html": "<b>{name}</b><br/>{type}", "style": {"backgroundColor": "#1e293b", "color": "white"}}
                        
                        st.pydeck_chart(pdk.Deck(
                            map_style="https://www.onemap.gov.sg/maps/json/raster/mbstyle/Original.json",
                            initial_view_state=view_state,
                            layers=[layer],
                            tooltip=tooltip
                        ))
                else:
                    # Helpful debug message so you know exactly what failed
                    st.caption(f"Map data unavailable. (Tried to search: '{proj_name}')")

    # Expanders
    with st.expander("🔍 View Retrieved RAG Context"):
        rates_context = get_application_rates_context()
        context = response.get("policy_context", rates_context) if isinstance(response, dict) else rates_context
        if context:
            st.code(context, language="markdown")
        else:
            st.warning("No application rates context available.")
            
    if isinstance(response, dict) and "messages" in response and response["messages"]:
        last_msg = response["messages"][-1]
        if hasattr(last_msg, "response_metadata") and "usage" in last_msg.response_metadata:
            usage = last_msg.response_metadata["usage"]
            cost = tracker.calculate_cost(usage)
            st.caption(f"⚡ Token Cost: ${cost:.5f} USD | Total Tokens: {usage.get('total_tokens', 0)}")
