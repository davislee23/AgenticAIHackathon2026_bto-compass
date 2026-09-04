# src/state.py
from typing import TypedDict, List, Dict, Any, Optional

class BTOState(TypedDict, total=False):
    applicant: Dict[str, Any]
    projects: List[Dict[str, Any]]
    application_rates: Dict[str, float]
    application_rates_context: str
    eligible_projects: List[Dict[str, Any]]
    rankings: List[Dict[str, Any]]
    explanation: str
    policy_context: str
    rates_raw_text: str
    messages: List[Any]
    data_changed: bool
    iteration_count: int
