# src/tools/tools.py
from langchain_core.tools import tool
from src.rag.rag_retriever import retrieve_policy
from src.engine import calculate_ehg_grant

@tool
def search_hdb_policies(query: str) -> str:
    """Searches official HDB eligibility rules and housing policy documentation."""
    return retrieve_policy(query)
    
