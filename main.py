import asyncio
import sqlite3
import random
import json  # Essential for passing valid data to AI
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

# --- 3. BACKGROUND TASK: FLEET SIMULATION (REAL-TIME UPDATES) ---
async def fleet_simulation_loop():
    """
    Simulates real-world driving. 
    Every 10 seconds, it updates odometer and fluctuates engine temp for all cars.
    """
    print("🚗 [Sim] Starting Fleet Physics Engine...")
    while True:
        await asyncio.sleep(10) # Update every 10s
        try:
            conn = sqlite3.connect("fleet_data.db")
            cur = conn.cursor()
            
            # 1. Increment Odometer (Driving)
            cur.execute("UPDATE vehicles SET odometer = odometer + 1")
            
            # 2. Fluctuate Temp (Random physics)
            # Vehicles with P0118 (Coolant issue) get hotter faster!
            cur.execute("UPDATE vehicles SET engine_temp = engine_temp + 2 WHERE error_code = 'P0118' AND engine_temp < 135")
            cur.execute("UPDATE vehicles SET engine_temp = engine_temp - 1 WHERE error_code = 'P0118' AND engine_temp > 130") # Thermostat cycling
            
            # Normal cars stay cool (fluctuate between 88-92)
            cur.execute("UPDATE vehicles SET engine_temp = 90 + (ABS(RANDOM()) % 5) WHERE error_code = 'None'")
            
            conn.commit()
            conn.close()
            # print("🔄 [Sim] Fleet Telematics Updated") # Uncomment to see heartbeat
        except Exception as e:
            print(f"⚠️ [Sim Error] {e}")

# Start simulation on app launch
@app.on_event("startup")
async def start_sim():
    asyncio.create_task(fleet_simulation_loop())

# --- 4. PROACTIVE MONITORING ---
def get_monitored_vehicles():
    """Fetches all vehicle IDs from the database."""
    try:
        conn = sqlite3.connect("fleet_data.db")
        cur = conn.cursor()
        cur.execute("SELECT vehicle_id FROM vehicles")
        rows = cur.fetchall()
        conn.close()
        return [r[0] for r in rows]
    except:
        return ["Vehicle-123"] # Fallback

async def proactive_health_check():
    print("\n🔍 [System] Running proactive fleet health check...")
    
    # 1. Clear old alerts so the frontend shows the FRESH state of the fleet.
    # This prevents the "Vehicle 123 only" bug if 108 was trapped in an old state.
    active_alerts.clear() 
    
    # Dynamic list from DB
    monitored_vehicles = get_monitored_vehicles()
    
    for vid in monitored_vehicles:
        # 2. Fetch data directly using the Real SQL Tool
        try:
            # We invoke the tool directly to get the dictionary
            data = fetch_telematics_data.invoke({"vehicle_id": vid})
            
            if "error" in data: continue

            # 3. Rule Engine Trigger (Threshold: 110°C)
            if data.get("engine_temp", 0) > 110:
                print(f"🚨 [Alert] Critical anomaly detected for {vid} (Temp: {data['engine_temp']}°C)!")
                
                # Generate a unique ID for this specific alert event
                alert_thread_id = f"alert_{vid}_{int(asyncio.get_event_loop().time())}"

                # --- SEEDING MEMORY ---
                # We construct a fake history so the Agent "remembers" doing the work.
                tool_call_id = f"call_init_{vid}" # Unique ID per vehicle
                
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
                        # 2. Fake the Tool returning the REAL SQL data
                        ToolMessage(
                            content=json.dumps(data), 
                            tool_call_id=tool_call_id
                        )
                    ],
                    "is_proactive": True 
                }
                
                config = {"configurable": {"thread_id": alert_thread_id}}
                
                try:
                    # Run the Agent (recursion limit prevents infinite loops)
                    # It will now flow: Diag -> Quality -> Scheduler -> STOP
                    result = await agent_app.ainvoke(inputs, config={**config, "recursion_limit": 25})
                    
                    final_response = result["messages"][-1].content
                    
                    active_alerts.append({
                        "vehicle_id": vid,
                        "severity": "CRITICAL",
                        "message": final_response, # Contains "Recommended... Slots: [9:00, 10:00]"
                        "timestamp": "Just now",
                        "thread_id": alert_thread_id
                    })
                except Exception as e:
                    print(f"❌ [Error] Agent crashed on {vid}: {e}")
        except Exception as e:
            print(f"⚠️ [Check Error] Skipping {vid}: {e}")

# --- SCHEDULER (DISABLED FOR MANUAL TESTING) ---
scheduler = AsyncIOScheduler()
scheduler.add_job(proactive_health_check, 'interval', seconds=60) 

# --- 5. API ENDPOINTS ---

@app.get("/")
async def root():
    return {"status": "Fleet Command AI is Online", "monitored_vehicles": get_monitored_vehicles()}

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

# --- 6. EXECUTION ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)