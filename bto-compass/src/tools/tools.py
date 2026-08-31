# src/tools/tools.py
from langchain_core.tools import tool

@tool
def calculate_cpf_housing_grant(monthly_income: float, is_first_timer: bool) -> str:
    """Calculates eligible CPF Housing Grants (EHG) for Singapore BTO applicants.
    
    Args:
        monthly_income: Average gross monthly household income over 12 months in SGD.
        is_first_timer: True if both applicants are first-time BTO buyers.
    """
    if not is_first_timer or monthly_income > 9000:
        return "Eligible Grant: $0 SGD (Income exceeds ceiling or not a first-timer)."
    
    if monthly_income <= 1500:
        grant = 80000
    elif monthly_income <= 9000:
        grant = 80000 - ((monthly_income - 1500) // 500) * 5000
    else:
        grant = 0
        
    return f"Eligible Enhanced CPF Housing Grant (EHG): ${grant:,.2f} SGD"

@tool
def find_bto_flats(budget: float, town: str = None) -> str:
    """Finds available BTO flats matching the user's budget and town preference."""
    # Placeholder implementation until dataset/retriever logic is connected
    return f"Found matching BTO flats under SGD ${budget:,.2f} in {town or 'all locations'}."

@tool
def search_hdb_policies(query: str) -> str:
    """Searches official HDB eligibility rules and housing policy documentation."""
    # Placeholder implementation until RAG retriever is connected
    return f"HDB Policy Search results for: '{query}'."
