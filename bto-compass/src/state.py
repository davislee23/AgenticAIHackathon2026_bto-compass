# src/state.py
from typing import TypedDict, List, Dict, Any

class BTOState(TypedDict, total=False):
    messages: List[Any]
    applicant: Dict[str, Any]
    projects: List[Dict[str, Any]]
    application_rates: Dict[str, float]
    eligible_projects: List[Dict[str, Any]]
    rankings: List[Dict[str, Any]]
    explanation: str
