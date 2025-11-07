import requests
import json
import os
from datetime import datetime
from .graph_state import AgentState

UEBA_LOG = 'data/ueba_audit.log'
RCA_LOG = 'data/manufacturing_feedback.log'
os.makedirs('data', exist_ok=True)

def diagnosis_node(state: AgentState) -> dict:
    """
    Calls the Diagnosis Agent API to get a risk assessment.
    """
    print("--- (Node: Diagnosis) ---")
    try:
        tick = state['telemetry_data']
        
        # Print the exact payload we are about to send
        print(f"DEBUG: Sending to /diagnose: {json.dumps(tick)}")
        
        resp = requests.post('http://localhost:8000/diagnose', json=tick, timeout=5)
        
        resp.raise_for_status() # Raise an exception for bad status codes
        diagnosis = resp.json()
        print(f"Diagnosis for {tick['vin']}: {diagnosis}")
        return {"diagnosis_result": diagnosis}
    except Exception as e:
        print(f"Diagnosis node error: {e}")
        return {"diagnosis_result": {"risk": 0.0, "error": str(e)}}

def ueba_check_node(state: AgentState) -> dict:
    """
    Performs a simple UEBA check before engaging the customer.
    """
    print("--- (Node: UEBA Check) ---")
    decision = 'allow'
    reason = 'policy_ok'
    
    # --- START: UEBA DEMO MODIFICATION ---
    # UEBA DEMO RULE: Check for a 'force_block' flag in the telemetry payload
    # This simulates detecting an anomalous payload or unauthorized request
    if state.get('telemetry_data', {}).get('force_block', False):
        decision = 'block'
        reason = "Demo: 'force_block' flag detected in payload"
    # --- END: UEBA DEMO MODIFICATION ---

    # Log the audit decision
    with open(UEBA_LOG, 'a') as f:
        log_entry = json.dumps({
            'timestamp': datetime.now().isoformat(),
            'agent': 'MasterOrchestrator',
            'action': 'customer_engagement',
            'target_vin': state['vin'],
            'decision': decision,
            'reason': reason
        })
        f.write(log_entry + '\n')
        
    print(f"UEBA Decision: {decision}")
    return {"ueba_decision": decision}

def customer_engagement_node(state: AgentState) -> dict:
    """
    Calls the Customer Engagement Agent, which simulates a voice call
    and auto-books a slot (based on scaffold logic).
    """
    print("--- (Node: Customer Engagement) ---")
    try:
        diag = state['diagnosis_result']
        vin = state['vin']
        
        # This endpoint, per the scaffold, simulates engagement AND books a slot
        resp = requests.post(
            'http://localhost:8000/engage', 
            json={'vin': vin, 'diag': diag}
        )
        resp.raise_for_status()
        booking = resp.json()
        print(f"Engagement/Booking result: {booking}")
        return {"booking_confirmation": booking}
    except Exception as e:
        print(f"Engagement node error: {e}")
        return {"booking_confirmation": {"status": "error", "msg": str(e)}}

def rca_insights_node(state: AgentState) -> dict:
    """
    (New) Generates RCA/CAPA insights for the manufacturing team.
    This fulfills a key deliverable.
    """
    print("--- (Node: RCA Insights) ---")
    insight = "No insight generated."
    try:
        diag = state['diagnosis_result']
        component = diag.get('component')
        
        # DEMO LOGIC: If a specific component fails, log it for RCA
        if component == 'Thermostat' and state.get('booking_confirmation', {}).get('status') == 'ok':
            insight = f"[INSIGHT] Recurring 'Thermostat' failure (P0128) detected and booked for VIN {state['vin']}. Flagging for manufacturing review."
            
            # Write to the manufacturing feedback log
            with open(RCA_LOG, 'a') as f:
                f.write(f"{datetime.now().isoformat()} - {insight}\n")
            
            print(f"RCA Insight: {insight}")
    except Exception as e:
        print(f"RCA node error: {e}")
        insight = "Error generating insight."
        
    return {"rca_insight": insight}