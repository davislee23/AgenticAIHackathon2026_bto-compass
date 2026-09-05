# src/tools/onemap.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()


def get_onemap_token() -> str:
    """Retrieves the static OneMap API token directly from the .env environment variable."""
    token = os.getenv("ONEMAP_API_TOKEN", "").strip()
    if not token:
        print("[ONEMAP] Warning: ONEMAP_API_TOKEN is missing or empty in your .env file.")
    return token


def geocode_address(address: str):
    """Geocodes an address string to (latitude, longitude) using OneMap API."""
    url = f"https://www.onemap.gov.sg/api/common/elastic/search?searchVal={address}&returnGeom=Y&getAddrDetails=Y&pageNum=1"
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            results = response.json().get("results", [])
            if results:
                lat = float(results[0]["LATITUDE"])
                lng = float(results[0]["LONGITUDE"])
                return (lat, lng)
    except Exception as e:
        print(f"[ONEMAP] Geocoding error for '{address}': {e}")
        
    return None


def get_nearest_mrt_stops(lat: float, lng: float, radius_m: int = 2000):
    """Retrieves nearest MRT stops around given coordinates within radius_m."""
    token = get_onemap_token()
    headers = {"Authorization": token} if token else {}
    
    url = f"https://www.onemap.gov.sg/api/public/revgeocode/mrt?latitude={lat}&longitude={lng}&radius={radius_m}"
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json().get("SearchResult", [])
    except Exception as e:
        print(f"[ONEMAP] Nearest MRT lookup failed: {e}")
        
    return []


def check_theme_status(query_name: str, date_time: str = "2023-01-01T00:00:00.000Z"):
    """Checks whether a specific theme has been updated since a given ISO timestamp."""
    token = get_onemap_token()
    headers = {"Authorization": token} if token else {}

    url = f"https://www.onemap.gov.sg/api/public/themesvc/checkThemeStatus?queryName={query_name}&dateTime={date_time}"
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"[ONEMAP] Check theme status failed: {e}")
        
    return None


def get_theme_data(query_name: str):
    """
    Retrieves spatial features for a specific OneMap theme.
    Common queryNames: 'kindergartens', 'hawkercentre', 'national_parks', 'primary_schools'
    """
    token = get_onemap_token()
    headers = {"Authorization": token} if token else {}

    url = f"https://www.onemap.gov.sg/api/public/themesvc/retrieveTheme?queryName={query_name}"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("SrchResults", [])
    except Exception as e:
        print(f"[ONEMAP] Retrieve theme '{query_name}' failed: {e}")
        
    return []


def find_nearby_amenities(query_name: str):
    """Alias for get_theme_data to maintain compatibility with tools.py imports."""
    return get_theme_data(query_name)
