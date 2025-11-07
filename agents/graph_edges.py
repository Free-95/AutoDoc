from .graph_state import AgentState

RISK_THRESHOLD = 0.7 # Engage if risk is 70% or higher

def should_engage(state: AgentState) -> str:
    """
    Conditional edge: Checks if the diagnosis risk is high enough
    to warrant customer engagement.
    """
    print("--- (Edge: Should Engage?) ---")
    risk = state.get('diagnosis_result', {}).get('risk', 0)
    
    if risk >= RISK_THRESHOLD:
        print(f"Risk {risk} >= {RISK_THRESHOLD}. Proceeding to UEBA check.")
        return "ueba_check_node"
    else:
        print(f"Risk {risk} < {RISK_THRESHOLD}. Ending flow.")
        return "end"

def is_allowed(state: AgentState) -> str:
    """
    Conditional edge: Checks the UEBA decision.
    """
    print("--- (Edge: Is Allowed?) ---")
    decision = state.get('ueba_decision', 'block')
    
    if decision == 'allow':
        print("UEBA allowed. Proceeding to engagement.")
        return "customer_engagement_node"
    else:
        print("UEBA blocked. Ending flow.")
        return "end"