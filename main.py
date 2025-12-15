import asyncio
from typing import List, Dict
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
# Import ToolMessage for proper history injection
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# Import the Agent Graph (now with Memory) from agents.py
from agents import app as agent_app, fetch_telematics_data

# --- 1. SETUP ---
app = FastAPI(title="Fleet Command AI Backend")

# In-memory storage for demo purposes
conversation_history: Dict[str, List] = {}
active_alerts: List[Dict] = []
monitored_vehicles = ["Vehicle-123"]

# --- 2. DATA MODELS ---
class ChatRequest(BaseModel):
    message: str
    thread_id: str
    vehicle_id: str = "Vehicle-123"

class Alert(BaseModel):
    vehicle_id: str
    severity: str
    message: str
    thread_id: str

# --- 3. BACKGROUND TASK: PROACTIVE MONITORING ---
async def proactive_health_check():
    print("\n🔍 [System] Running proactive fleet health check...")
    for vid in monitored_vehicles:
        # 1. Fetch data directly (Synchronous tool call is fine here)
        data = fetch_telematics_data.invoke({"vehicle_id": vid})
        
        # 2. Rule Engine Trigger
        if data.get("engine_temp", 0) > 110:
            print(f"🚨 [Alert] Critical anomaly detected for {vid}!")
            
            # Generate a specific ID for this event
            alert_thread_id = f"alert_{vid}_{int(asyncio.get_event_loop().time())}"

            # --- SEEDING MEMORY ---
            # We construct a fake history so the Agent "remembers" doing the work.
            # This is critical for the MemorySaver to pick up the context later.
            tool_call_id = "call_init_123" 
            
            inputs = {
                "messages": [
                    HumanMessage(content=f"System Alert: Check vehicle {vid}."),
                    # 1. Fake the AI trying to call the tool
                    AIMessage(
                        content="", 
                        tool_calls=[{
                            "name": "fetch_telematics_data", 
                            "args": {"vehicle_id": vid}, 
                            "id": tool_call_id
                        }]
                    ),
                    # 2. Fake the Tool returning the data
                    ToolMessage(
                        content=str({
                            "vehicle_id": vid, 
                            "engine_temp": data['engine_temp'], 
                            "error_code": data['error_code']
                        }),
                        tool_call_id=tool_call_id
                    )
                ],
                "is_proactive": True 
            }
            
            config = {"configurable": {"thread_id": alert_thread_id}}
            
            try:
                # Run the Agent to get the Diagnosis and Quality Check
                # Recursion limit prevents infinite loops
                result = await agent_app.ainvoke(inputs, config={**config, "recursion_limit": 20})
                
                final_response = result["messages"][-1].content
                active_alerts.append({
                    "vehicle_id": vid,
                    "severity": "CRITICAL",
                    "message": final_response,
                    "timestamp": "Just now",
                    "thread_id": alert_thread_id
                })
            except Exception as e:
                print(f"❌ [Error] Agent crashed on {vid}: {e}")

# --- SCHEDULER (DISABLED FOR MANUAL TESTING) ---
scheduler = AsyncIOScheduler()
scheduler.add_job(proactive_health_check, 'interval', seconds=60) 

# @app.on_event("startup")
# async def start_scheduler():
#     scheduler.start()

# --- 4. API ENDPOINTS ---

@app.get("/")
async def root():
    return {"status": "Fleet Command AI is Online", "monitored_vehicles": monitored_vehicles}

@app.post("/trigger_check")
async def manual_trigger():
    """Manually run the health check via Frontend Button."""
    await proactive_health_check()
    return {"status": "Check triggered"}

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Main endpoint for User <-> Agent interaction.
    """
    print(f"📩 [Chat] Received: {request.message} (Thread: {request.thread_id})")
    
    # --- CONTEXT INJECTION ---
    # We remind the agent which vehicle we are talking about.
    augmented_message = f"Regarding {request.vehicle_id}: {request.message}"

    inputs = {
        "messages": [HumanMessage(content=augmented_message)],
        # CRITICAL: We flip this to False so the Scheduler is allowed to act
        "is_proactive": False 
    }
    
    config = {"configurable": {"thread_id": request.thread_id}}
    
    try:
        # The MemorySaver in agents.py will automatically load the previous history
        result = await agent_app.ainvoke(inputs, config=config)
        ai_response = result["messages"][-1].content
        return {"response": ai_response, "vehicle_id": request.vehicle_id}
        
    except Exception as e:
        print(f"❌ [Server Error] {e}") 
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts")
async def get_alerts():
    """Frontend polls this to show "Red" notifications."""
    return active_alerts

# --- 5. EXECUTION ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)