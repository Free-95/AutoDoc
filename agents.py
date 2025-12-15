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
    """Fetches LIVE data from the SQL Fleet Database."""
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
    # Fetch all CAPA records to check for matches
    rows = query_db("SELECT * FROM capa_records")
    
    matches = []
    for row in rows:
        # Check if the component or defect listed in DB is mentioned in the diagnosis
        if row["component"] in diagnosis or row["defect_type"] in diagnosis:
            matches.append(f"RCA INSIGHT: Batch {row['batch_id']} - {row['action_required']} (CAPA Match)")
            
    if matches:
        return " ".join(matches)
        
    # Fallback logic if DB lookup misses specific keywords but issue is known
    if "Coolant" in diagnosis:
         return "RCA INSIGHT: Potential Coolant Leak. Check CAPA-992 (Water Pump Seal)."
    return "No recurring manufacturing defects found in CAPA DB."

@tool
def check_schedule_availability():
    """Queries OPEN slots from appointments table."""
    # Get the next 4 unbooked slots
    rows = query_db("SELECT slot_time FROM appointments WHERE is_booked = 0 LIMIT 4")
    
    if not rows:
        return "No slots available in the system."
    
    slots = [row["slot_time"] for row in rows]
    return f"OPEN SLOTS: {slots}"

@tool
def book_appointment(slot: str, vehicle_id: str):
    """Books the appointment. Handles fuzzy time matching (e.g., '9am' -> '09:00')."""
    # 1. Normalize the input
    clean_slot = slot.lower().replace("am", "").replace("pm", "").strip()
    
    # Pad single digit hours (e.g., "9:00" -> "09:00")
    if ":" in clean_slot:
        hour, minute = clean_slot.split(":")
        if len(hour) == 1:
            clean_slot = f"0{hour}:{minute}"
    
    # If user typed just "9", treat it as "09:00"
    if ":" not in clean_slot and len(clean_slot) <= 2:
         clean_slot = f"{int(clean_slot):02d}:00"

    print(f"  [Tool] Attempting to book '{slot}' (Normalized: '{clean_slot}')...")

    # 2. Try to find a matching OPEN slot in the DB
    existing = query_db(
        "SELECT id, slot_time FROM appointments WHERE slot_time LIKE ? AND is_booked = 0", 
        (f"%{clean_slot}%",), 
        one=True
    )
    
    if not existing:
        return f"Slot unavailable. Please pick another time from the list."
    
    # 3. Book it
    query_db("UPDATE appointments SET is_booked = 1, booked_vehicle_id = ? WHERE id = ?", (vehicle_id, existing["id"]))
    
    return f"BOOKING COMPLETE: {vehicle_id} scheduled for {existing['slot_time']}."

@tool
def update_vehicle_status(vehicle_id: str, status: str):
    """Updates the vehicle status in the database."""
    query_db("UPDATE vehicles SET status = ? WHERE vehicle_id = ?", (status, vehicle_id))
    return f"Status for {vehicle_id} updated to {status}."

# --- DUMMY TOOLS (Safety Net) ---
# FIX: Added docstrings to these functions to resolve ValueError

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
    tools=[fetch_telematics_data, brave_search], 
    prompt="You are a Data Retrieval Bot. If vehicle ID is known, call tool. Output data summary and STOP."
)

# UPDATED: Diagnostician must be descriptive
diagnostician = create_react_agent(
    llm_worker, 
    tools=[diagnose_issue, update_vehicle_status, send_alert_to_maintenance_team, fetch_telematics_data, brave_search], 
    prompt=(
        "You are a Diagnostician. "
        "1. Analyze the tool output data. If Temp > 110, it is CRITICAL. "
        "2. Output a CLEAR, HUMAN-READABLE diagnosis (e.g., 'Detected Engine Overheating due to Sensor Failure'). "
        "3. DO NOT just say 'Critical'. Explain WHY based on the tool output."
    )
)

quality_engineer = create_react_agent(
    llm_worker, 
    tools=[get_rca_insights], 
    prompt="You are a Quality Engineer. Call tool ONCE. Then start response with 'QUALITY CHECK COMPLETE'."
)

# UPDATED: Scheduler automatically shows slots
scheduler = create_react_agent(
    llm_worker, 
    tools=[check_schedule_availability, book_appointment, send_notification_to_owner, update_vehicle_status], 
    prompt=(
        "You are a Service Scheduler. "
        "1. If 'QUALITY CHECK COMPLETE' is in history, call 'check_schedule_availability' immediately. "
        "2. Output EXACTLY: 'Service Recommended. Available slots: [List Slots]'. "
        "3. Do NOT ask 'Would you like to proceed?'. Just present the slots."
        "4. If user provides a time, call 'book_appointment'."
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
        
        # 1. Diag -> Quality
        if "CRITICAL" in content and "QUALITY CHECK COMPLETE" not in history_str:
            return {"next": "QualityEngineer"}
            
        # 2. Quality -> Scheduler (AUTO-FETCH SLOTS)
        if "QUALITY CHECK COMPLETE" in content:
            # If we haven't shown slots yet, go to scheduler
            if "Available slots" not in history_str and "OPEN SLOTS" not in history_str:
                return {"next": "Scheduler"}
            else:
                 return {"next": "FINISH"} 

        # 3. Scheduler (Slots Shown) -> Stop
        if "Available slots" in content or "OPEN SLOTS" in content:
            return {"next": "FINISH"}

        # 4. Booking Done -> Feedback
        if "BOOKING COMPLETE" in content:
            if is_proactive: return {"next": "FINISH"}
            return {"next": "FeedbackAgent"}

        return {"next": "FINISH"}

    # --- CASE 2: HUMAN JUST SPOKE ---
    
    # 1. Missing basic data? -> Data Analyst
    if "Engine Temp" not in history_str and "error_code" not in history_str:
        return {"next": "DataAnalyst"}

    # 2. Data present, but no diagnosis? -> Diagnostician
    if "CRITICAL" not in history_str and "Status: Normal" not in history_str:
        return {"next": "Diagnostician"}

    # 3. Critical issue, but Quality not checked? -> Quality Engineer
    if "CRITICAL" in history_str and "QUALITY CHECK COMPLETE" not in history_str:
        return {"next": "QualityEngineer"}

    # 4. Quality done, but not booked? -> Scheduler
    if "QUALITY CHECK COMPLETE" in history_str and "BOOKING COMPLETE" not in history_str:
        return {"next": "Scheduler"}

    # 5. Booking done, but no feedback? -> Feedback Agent
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