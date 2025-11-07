from typing import TypedDict, Optional, Dict, Any

class AgentState(TypedDict):
    """
    Represents the state of the agentic workflow.
    """
    vin: str
    telemetry_data: Dict[str, Any]
    diagnosis_result: Optional[Dict[str, Any]]
    ueba_decision: Optional[str]
    booking_confirmation: Optional[Dict[str, Any]]
    rca_insight: Optional[str]