# src/state.py
from typing import TypedDict, List, Dict, Any, Optional

class BTOState(TypedDict, total=False):
    messages: List[Any]
    applicant: Dict[str, Any]
    projects: List[Dict[str, Any]]
    eligible_projects: List[Dict[str, Any]]
    rankings: List[Dict[str, Any]]
    application_rates: Dict[str, float]
    rates_raw_text: Optional[str]
    explanation: Optional[str]
    policy_context: Optional[str]
