import operator
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

# --- 2. DEFINE TOOLS ---
@tool
def fetch_telematics_data(vehicle_id: str):
    """Fetches real-time sensor data, maintenance logs, and error codes."""
    if vehicle_id == "Vehicle-123":
        return {
            "vehicle_id": vehicle_id,
            "engine_temp": 115, 
            "error_code": "P0118",
            "maintenance_history": ["Oil change 3 months ago"],
            "odometer": 45000
        }
    return {"vehicle_id": vehicle_id, "engine_temp": 90, "error_code": "None"}

@tool
def diagnose_issue(error_code: str, engine_temp: int):
    """Analyzes diagnostic trouble codes (DTC) and sensor readings."""
    if engine_temp is None: return "ERROR: Missing Data."
    if engine_temp > 110 or error_code == "P0118":
        return "CRITICAL: High Probability of Coolant Sensor Failure."
    return "Status: Normal."

# --- DUMMY TOOLS (The Safety Net) ---
@tool
def brave_search(query: str):
    """Performs a web search."""
    return "Offline Mode: Internet unavailable. Please use internal diagnosis tools."

@tool
def update_vehicle_status(vehicle_id: str, status: str):
    """Updates the vehicle status in the database."""
    return f"Status for {vehicle_id} updated to {status}."

@tool
def send_notification_to_owner(vehicle_id: str, message: str):
    """Sends a notification to the vehicle owner."""
    return "Notification sent."

@tool
def send_alert_to_maintenance_team(vehicle_id: str, message: str):
    """Sends an alert to the maintenance team."""
    return "Alert sent."

@tool
def get_rca_insights(diagnosis: str):
    """Queries the Manufacturing CAPA database."""
    if "Coolant" in diagnosis:
        return "ALERT: Batch #992 Water Pumps have a known seal defect. CAPA #402: Use upgraded gaskets."
    return "No recurring manufacturing defects found."

@tool
def check_schedule_availability():
    """Checks for open service slots."""
    return "Available Slots: [Tomorrow 10am, Tomorrow 2pm]"

@tool
def book_appointment(slot: str, vehicle_id: str):
    """Books the appointment."""
    valid_slots = ["Tomorrow 10am", "Tomorrow 2pm"]
    normalized_slot = slot.strip()
    is_valid = any(v.lower() in normalized_slot.lower() for v in valid_slots)
    if not is_valid: return "Slot unavailable"
    return f"BOOKING COMPLETE: Service booked for {vehicle_id} at {slot}."

@tool
def log_customer_feedback(feedback: str, rating: int):
    """Logs post-interaction customer satisfaction to the database."""
    return "Feedback saved."

# --- 3. STATE DEFINITION ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next: str
    security_risk: bool
    is_proactive: bool 

# --- 4. UEBA SECURITY ---
def ueba_guardrail_node(state: AgentState):
    messages = state["messages"]
    if isinstance(messages[-1], HumanMessage):
        if "drop table" in messages[-1].content.lower():
            return {"security_risk": True, "messages": [AIMessage(content="SECURITY ALERT: Blocked.")]}
    return {"security_risk": False}

# --- 5. WORKER AGENTS (HARDENED PROMPTS) ---

data_analyst = create_react_agent(
    llm_worker, 
    tools=[fetch_telematics_data, brave_search], 
    prompt="You are a Data Retrieval Bot. If vehicle ID is known, call tool. Output data summary and STOP."
)

# UPDATED: Strict instructions to never ask questions
diagnostician = create_react_agent(
    llm_worker, 
    tools=[diagnose_issue, update_vehicle_status, send_alert_to_maintenance_team, fetch_telematics_data, brave_search], 
    prompt=(
        "You are a strict technical system. "
        "Analyze the tool output data. "
        "1. If 'engine_temp' is None or data is missing, output EXACTLY: 'Insufficient Data'. "
        "2. Do NOT be polite. Do NOT ask for IDs. Do NOT offer to help. "
        "3. If CRITICAL, you may update status or send alerts."
    )
)

quality_engineer = create_react_agent(
    llm_worker, 
    tools=[get_rca_insights], 
    prompt="You are a Quality Engineer. Call tool ONCE. Then start response with 'QUALITY CHECK COMPLETE'."
)

# UPDATED: Strict instructions to stop negotiating
scheduler = create_react_agent(
    llm_worker, 
    tools=[check_schedule_availability, book_appointment, send_notification_to_owner, update_vehicle_status], 
    prompt=(
        "You are a Scheduler. "
        "1. If user provides a time, call 'book_appointment'. "
        "2. If tool returns 'Slot unavailable', output ONLY 'Slot unavailable'. DO NOT offer alternatives. "
        "3. If user says 'Yes', reply: 'I can help. Available slots are Tomorrow 10am and 2pm.' "
    )
)

feedback_agent = create_react_agent(llm_worker, tools=[log_customer_feedback], prompt="Log feedback and say goodbye.")

# --- 6. SUPERVISOR ---
members = ["DataAnalyst", "Diagnostician", "QualityEngineer", "Scheduler", "FeedbackAgent"]

system_prompt = (
    "You are a Supervisor. Select the next agent."
)

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
    Hybrid Supervisor: distinct logic for AI turns vs Human turns to prevent loops.
    """
    if state.get("security_risk"): return {"next": "FINISH"}
    
    messages = state["messages"]
    last_msg = messages[-1]
    history_str = " ".join([m.content for m in messages])
    is_proactive = state.get("is_proactive", False)

    # --- CASE 1: LAST MESSAGE WAS FROM AN AGENT (AI) ---
    # We generally want to STOP here to let the user reply, 
    # unless we need to chain agents together (e.g. Diag -> Quality).
    if isinstance(last_msg, AIMessage):
        content = last_msg.content
        
        # Chain: If Diagnosis found Critical issue -> Go to Quality immediately
        if "CRITICAL" in content and "QUALITY CHECK COMPLETE" not in history_str:
            return {"next": "QualityEngineer"}
        
        # Chain: If Booking just finished -> Go to Feedback immediately
        if "BOOKING COMPLETE" in content:
            if is_proactive: return {"next": "FINISH"}
            return {"next": "FeedbackAgent"}

        # DEFAULT: If the Agent just spoke (e.g. Scheduler offered slots), 
        # we STOP ("FINISH") so the user can type their reply.
        return {"next": "FINISH"}

    # --- CASE 2: LAST MESSAGE WAS FROM HUMAN (User Input) ---
    # The user just typed something. We decide who handles it based on state.
    
    # 1. Missing basic data? -> Data Analyst
    if "Engine Temp" not in history_str and "error_code" not in history_str:
        return {"next": "DataAnalyst"}

    # 2. Data present, but no diagnosis? -> Diagnostician
    # (Check if we have "CRITICAL" or "Normal" in history)
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

    # Fallback
    return {"next": "FINISH"}

# --- 7. GRAPH ---
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