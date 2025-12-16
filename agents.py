import operator
import sqlite3
from typing import Annotated, List, Literal, TypedDict, Union

from langchain_ollama import ChatOllama
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver 
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# --- 1. CONFIGURATION ---
print("🔌 Connecting to Local Ollama (Qwen 2.5)...")

llm_supervisor = ChatOllama(
    model="qwen2.5:7b", 
    temperature=0,
    base_url="http://localhost:11434"
)

llm_worker = ChatOllama(
    model="qwen2.5:7b", 
    temperature=0,
    base_url="http://localhost:11434"
)

# --- 2. DATABASE HELPER ---
DB_NAME = "fleet_data.db"

def query_db(query, args=(), one=False):
    """Helper to run SQL queries against the fleet database."""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row # Access columns by name
        cur = conn.cursor()
        cur.execute(query, args)
        if query.strip().upper().startswith("SELECT"):
            rv = cur.fetchall()
            conn.close()
            return (rv[0] if rv else None) if one else rv
        else:
            # For INSERT/UPDATE/DELETE
            conn.commit()
            conn.close()
            return cur.rowcount
    except Exception as e:
        return None

# --- 3. DEFINE REAL TOOLS (SQL INTEGRATED) ---

@tool
def fetch_telematics_data(vehicle_id: str):
    """Fetches LIVE data for a SINGLE vehicle from the SQL Fleet Database."""
    row = query_db("SELECT * FROM vehicles WHERE vehicle_id = ?", (vehicle_id,), one=True)
    
    if not row:
        return {"error": f"Vehicle ID '{vehicle_id}' not found in Fleet Database."}
    
    return {
        "vehicle_id": row["vehicle_id"],
        "model": row["model"],
        "engine_temp": row["engine_temp"],
        "oil_life": f"{row['oil_life']}%",
        "error_code": row["error_code"],
        "status": row["status"],
        "odometer": row["odometer"]
    }

@tool
def analyze_fleet_trends(scope: str = "all"):
    """
    Analyzes the ENTIRE fleet to forecast service center demand and workload.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Get Fleet Health Distribution
    cursor.execute("SELECT status, COUNT(*) FROM vehicles GROUP BY status")
    status_raw = cursor.fetchall()
    status_dist = {row[0]: row[1] for row in status_raw}

    # 2. Identify High-Risk Vehicles
    cursor.execute("SELECT vehicle_id, model, error_code FROM vehicles WHERE oil_life < 20 OR error_code != 'None'")
    high_risk_cars = cursor.fetchall()
    
    demand_count = len(high_risk_cars)
    estimated_hours = demand_count * 3 

    # 3. Get High Mileage Trends
    cursor.execute("SELECT AVG(odometer) FROM vehicles")
    avg_odometer = cursor.fetchone()[0]

    conn.close()

    return f"""
    📊 FLEET FORECAST REPORT
    ------------------------
    1. Health Overview: {status_dist}
    2. Immediate Service Demand: {demand_count} vehicles require attention.
       - Details: {[f"{c[0]} ({c[1]})" for c in high_risk_cars]}
    3. Projected Service Center Workload: {estimated_hours} Hours of labor required this week.
    4. Long-term Wear: Average fleet mileage is {int(avg_odometer):,} miles.
    
    RECOMMENDATION FOR SCHEDULER:
    {'🔴 Heavy Load - Open more slots immediately.' if demand_count > 3 else '🟢 Normal Load - Standard scheduling applies.'}
    """

@tool
def get_maintenance_history(vehicle_id: str):
    """Fetches historical service records for a specific vehicle."""
    rows = query_db("SELECT * FROM maintenance_history WHERE vehicle_id = ? ORDER BY service_date DESC LIMIT 5", (vehicle_id,))
    if not rows:
        return "No maintenance history found."
    return "\n".join([f"- {row['service_date']}: {row['service_type']} ({row['description']})" for row in rows])

@tool
def diagnose_issue(error_code: str, engine_temp: int):
    """Analyzes diagnostic trouble codes (DTC) and sensor readings."""
    if engine_temp is None: return "Insufficient Data"
    
    issues = []
    if engine_temp > 110:
        issues.append(f"CRITICAL OVERHEATING detected (Temp: {engine_temp}°C).")
    if error_code == "P0118":
        issues.append("Sensor Failure: Coolant Temperature Circuit High input.")
    if error_code == "P0420":
        issues.append("Catalyst System Efficiency Below Threshold.")
        
    if issues:
        return "DIAGNOSIS REPORT: " + " ".join(issues)
        
    return "Status: Normal. All parameters within operating limits."

@tool
def get_rca_insights(diagnosis: str):
    """Queries the Manufacturing CAPA database."""
    print(f"   [Tool] RCA Analysis running for: {diagnosis}")
    
    code_map = {
        "P0118": "Coolant Sensor",
        "P0420": "Catalytic Converter",
        "overheating": "Coolant Sensor"
    }
    
    search_terms = [diagnosis]
    
    for code, component in code_map.items():
        if code.lower() in diagnosis.lower():
            search_terms.append(component)
            
    rows = query_db("SELECT * FROM capa_records")
    
    matches = []
    for row in rows:
        for term in search_terms:
            if term in row["component"] or term in row["defect_type"] or row["component"] in term:
                matches.append(f"RCA INSIGHT: Batch {row['batch_id']} - {row['action_required']} (CAPA Match: {row['component']})")
                break 
            
    if matches:
        return " ".join(matches)
        
    return "No recurring manufacturing defects found in CAPA DB."

@tool
def check_schedule_availability():
    """Queries OPEN slots from appointments table."""
    rows = query_db("SELECT slot_time FROM appointments WHERE is_booked = 0 LIMIT 4")
    
    if not rows:
        return "No slots available in the system."
    
    slots = [row["slot_time"] for row in rows]
    return f"OPEN SLOTS: {slots}"

@tool
def book_appointment(slot: str, vehicle_id: str):
    """Books the appointment. Handles fuzzy time matching (e.g., '9am' -> '09:00')."""
    clean_slot = slot.lower().replace("am", "").replace("pm", "").strip()
    
    if ":" in clean_slot:
        hour, minute = clean_slot.split(":")
        if len(hour) == 1:
            clean_slot = f"0{hour}:{minute}"
    
    if ":" not in clean_slot and len(clean_slot) <= 2:
         clean_slot = f"{int(clean_slot):02d}:00"

    print(f"  [Tool] Attempting to book '{slot}' (Normalized: '{clean_slot}')...")

    existing = query_db(
        "SELECT id, slot_time FROM appointments WHERE slot_time LIKE ? AND is_booked = 0", 
        (f"%{clean_slot}%",), 
        one=True
    )
    
    if not existing:
        return f"Slot unavailable. Please pick another time from the list."
    
    query_db("UPDATE appointments SET is_booked = 1, booked_vehicle_id = ? WHERE id = ?", (vehicle_id, existing["id"]))
    
    return f"BOOKING COMPLETE: {vehicle_id} scheduled for {existing['slot_time']}."

@tool
def update_vehicle_status(vehicle_id: str, status: str):
    """Updates the vehicle status in the database."""
    query_db("UPDATE vehicles SET status = ? WHERE vehicle_id = ?", (status, vehicle_id))
    return f"Status for {vehicle_id} updated to {status}."

# --- DUMMY TOOLS (Safety Net) ---
@tool
def brave_search(query: str):
    """Performs a web search (Simulation Mode)."""
    return "Offline Mode: Internet unavailable. Please use internal diagnosis tools."

@tool
def send_notification_to_owner(vehicle_id: str, message: str):
    """Simulates sending an email/SMS notification to the vehicle owner."""
    return "Notification sent."

@tool
def send_alert_to_maintenance_team(vehicle_id: str, message: str):
    """Simulates sending a priority alert to the maintenance dashboard."""
    return "Alert sent."

@tool
def log_customer_feedback(feedback: str, rating: int):
    """Logs customer feedback for quality assurance."""
    return "Feedback saved."

@tool
def report_manufacturing_defect(component: str, issue_description: str, vehicle_id: str):
    """
    Feeds a new potential defect insight back to the Manufacturing/Quality team.
    Use this when multiple vehicles exhibit the same unexplained failure.
    """
    print(f"🏭 REPORTING TO FACTORY: Potential defect in {component} observed in {vehicle_id}: {issue_description}")
    return "Defect report submitted to Engineering Team for analysis."

# --- 4. STATE DEFINITION ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next: str
    security_risk: bool
    is_proactive: bool 

# --- 5. UEBA SECURITY ---
def ueba_guardrail_node(state: AgentState):
    messages = state["messages"]
    if isinstance(messages[-1], HumanMessage):
        if "drop table" in messages[-1].content.lower():
            return {"security_risk": True, "messages": [AIMessage(content="SECURITY ALERT: Blocked.")]}
    return {"security_risk": False}

# --- 6. WORKER AGENTS (UPDATED PROMPTS) ---

data_analyst = create_react_agent(
    llm_worker, 
    tools=[fetch_telematics_data, analyze_fleet_trends, get_maintenance_history, brave_search], 
    prompt=(
        "You are a Lead Data Analyst. "
        "1. If asked about a SPECIFIC vehicle, use 'fetch_telematics_data' and 'get_maintenance_history'. "
        "2. If asked about 'Fleet Status', 'Forecasting', or 'Demand', use 'analyze_fleet_trends'. "
        "3. Output the data summary clearly and then STOP."
    )
)

# UPDATED: NO QUESTIONS, JUST FACTS
diagnostician = create_react_agent(
    llm_worker, 
    tools=[diagnose_issue, update_vehicle_status, send_alert_to_maintenance_team, fetch_telematics_data, brave_search], 
    prompt=(
        "You are an empathetic but urgent Vehicle Health Expert. "
        "1. When identifying a CRITICAL issue, explain the RISK in plain English. "
        "2. DO NOT ASK 'Would you like to proceed?' or 'Should I book?'. "
        "3. Instead, state: 'I am alerting the maintenance team and checking appointment slots immediately.' "
        "4. Your job is to alarm the user enough to fix it, then STOP."
    )
)

# UPDATED: CONFIDENT
quality_engineer = create_react_agent(
    llm_worker, 
    tools=[get_rca_insights, report_manufacturing_defect], 
    prompt=(
        "You are a Senior Quality Engineer. "
        "1. Check 'get_rca_insights'. "
        "2. If a match is found, say: 'Good news—we have seen this before. It is a known issue with [Batch/Part].' "
        "3. State the solution clearly. "
        "4. End with 'QUALITY CHECK COMPLETE'."
    )
)

# UPDATED: THE CLOSER
scheduler = create_react_agent(
    llm_worker, 
    tools=[check_schedule_availability, book_appointment, send_notification_to_owner, update_vehicle_status], 
    prompt=(
        "You are a persuasive Service Concierge. "
        "1. Your goal is to secure the booking. Do NOT ask 'Do you want to proceed?'. "
        "2. Assume the user wants to book. Call 'check_schedule_availability' immediately. "
        "3. State: 'To prevent damage, I have located priority slots at [List Slots].' "
        "4. End with a specific Call to Action: 'Which of these times works best for you?'"
        "5. If user provides a time, call 'book_appointment'."
    )
)

feedback_agent = create_react_agent(llm_worker, tools=[log_customer_feedback], prompt="Log feedback and say goodbye.")

# --- 7. SUPERVISOR (UPDATED LOGIC) ---
members = ["DataAnalyst", "Diagnostician", "QualityEngineer", "Scheduler", "FeedbackAgent"]

system_prompt = "You are a Supervisor. Select the next agent."

class Router(BaseModel):
    next: Literal["DataAnalyst", "Diagnostician", "QualityEngineer", "Scheduler", "FeedbackAgent", "FINISH"]

supervisor_chain = (
    ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages"),
        ("system", "Metadata: is_proactive={is_proactive}"),
        ("system", "Who acts next? {options}"),
    ]).partial(options=str(members + ["FINISH"]))
    | llm_supervisor.with_structured_output(Router)
)

def supervisor_node(state: AgentState):
    """
    Hybrid Supervisor with Auto-Booking Logic.
    """
    if state.get("security_risk"): return {"next": "FINISH"}
    
    messages = state["messages"]
    last_msg = messages[-1]
    history_str = " ".join([m.content for m in messages])
    is_proactive = state.get("is_proactive", False)

    # --- CASE 1: AI JUST SPOKE (Turn-Taking) ---
    if isinstance(last_msg, AIMessage):
        content = last_msg.content
        
        # 0. Data Analyst -> STOP
        if "FLEET FORECAST REPORT" in content:
            return {"next": "FINISH"}

        # 1. Diag -> Quality
        if "CRITICAL" in content and "QUALITY CHECK COMPLETE" not in history_str:
            return {"next": "QualityEngineer"}
            
        # 2. Quality -> Scheduler (Always transition to booking options)
        if "QUALITY CHECK COMPLETE" in content:
            if "Available slots" not in history_str and "OPEN SLOTS" not in history_str:
                return {"next": "Scheduler"}
            else:
                 return {"next": "FINISH"} 

        # 3. Scheduler (Slots Shown) -> Stop and wait for user choice
        if "Available slots" in content or "OPEN SLOTS" in content:
            return {"next": "FINISH"}

        # 4. Booking Done -> Feedback
        if "BOOKING COMPLETE" in content:
            if is_proactive: return {"next": "FINISH"}
            return {"next": "FeedbackAgent"}

        return {"next": "FINISH"}

    # --- CASE 2: HUMAN JUST SPOKE ---
    user_text = last_msg.content.lower()

    # --- NEW: THE "YES" TRAP (Solves the looping issue) ---
    # If user says "Yes/Do it", and we haven't shown slots yet, FORCE Scheduler.
    if "yes" in user_text or "proceed" in user_text or "fix it" in user_text or "do it" in user_text:
        if "OPEN SLOTS" not in history_str and "Available slots" not in history_str:
            return {"next": "Scheduler"}
    
    # 0. Manufacturing Questions
    if "manufacturing" in user_text or "defect" in user_text or "common issue" in user_text or "rca" in user_text:
        return {"next": "QualityEngineer"}

    # 1. Fleet/Forecast request
    if "fleet" in user_text or "forecast" in user_text or "demand" in user_text:
        return {"next": "DataAnalyst"}

    # 2. Missing basic data
    if "Engine Temp" not in history_str and "error_code" not in history_str:
        return {"next": "DataAnalyst"}

    # 3. Data present, no diagnosis
    if "CRITICAL" not in history_str and "Status: Normal" not in history_str:
        return {"next": "Diagnostician"}

    # 4. Critical issue, Quality not checked
    if "CRITICAL" in history_str and "QUALITY CHECK COMPLETE" not in history_str:
        return {"next": "QualityEngineer"}

    # 5. Quality done, not booked
    if "QUALITY CHECK COMPLETE" in history_str and "BOOKING COMPLETE" not in history_str:
        return {"next": "Scheduler"}

    # 6. Booking done, no feedback
    if "BOOKING COMPLETE" in history_str and "Feedback saved" not in history_str:
         return {"next": "FeedbackAgent"}

    # Catch-All
    return {"next": "Scheduler"}

# --- 8. GRAPH ---
workflow = StateGraph(AgentState)
workflow.add_node("UEBA_Check", ueba_guardrail_node)
workflow.add_node("Supervisor", supervisor_node)
workflow.add_node("DataAnalyst", data_analyst)
workflow.add_node("Diagnostician", diagnostician)
workflow.add_node("QualityEngineer", quality_engineer)
workflow.add_node("Scheduler", scheduler)
workflow.add_node("FeedbackAgent", feedback_agent)

workflow.add_edge(START, "UEBA_Check")
workflow.add_conditional_edges("UEBA_Check", lambda s: END if s.get("security_risk") else "Supervisor")
workflow.add_conditional_edges("Supervisor", lambda s: s["next"], 
    {"DataAnalyst":"DataAnalyst", "Diagnostician":"Diagnostician", "QualityEngineer":"QualityEngineer", 
     "Scheduler":"Scheduler", "FeedbackAgent":"FeedbackAgent", "FINISH":END})

for m in members: workflow.add_edge(m, "Supervisor")

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)