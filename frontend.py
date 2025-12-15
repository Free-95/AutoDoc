import streamlit as st
import requests
import time
import uuid

# --- CONFIGURATION ---
BACKEND_URL = "http://localhost:8000"
st.set_page_config(
    page_title="Fleet Command AI", 
    page_icon="🚗",
    layout="wide"
)

# --- SESSION STATE INITIALIZATION ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# Generate a unique ID for this user session
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

# Track processed alerts
if "processed_alerts" not in st.session_state:
    st.session_state.processed_alerts = set()

# --- SIDEBAR: FLEET STATUS ---
with st.sidebar:
    st.header("📡 Fleet Telemetry")
    
    # 1. Fetch live status from Backend
    try:
        response = requests.get(f"{BACKEND_URL}/")
        if response.status_code == 200:
            data = response.json()
            st.success("🟢 System Online")
            
            # --- MANUAL TRIGGER BUTTON (THE MISSING PIECE) ---
            st.markdown("---")
            st.write("**Manual Controls**")
            if st.button("🔄 Run Health Check", type="primary"):
                with st.spinner("Scanning fleet sensors..."):
                    try:
                        # Call the trigger endpoint we made in main.py
                        trigger_res = requests.post(f"{BACKEND_URL}/trigger_check")
                        if trigger_res.status_code == 200:
                            st.success("Scan Initiated Successfully")
                        else:
                            st.error(f"Trigger Failed: {trigger_res.status_code}")
                    except Exception as e:
                        st.error(f"Connection Error: {e}")
            # -------------------------------------------------

            st.markdown("---")
            st.subheader("Monitored Assets")
            for vehicle in data.get("monitored_vehicles", []):
                st.code(f"🚛 {vehicle}")
        else:
            st.error("🔴 Backend Error")
    except requests.exceptions.ConnectionError:
        st.error("🔴 Backend Offline")
        st.info("Ensure main.py is running.")
        st.stop()

# --- MAIN DASHBOARD ---
st.title("🤖 Autonomous Service Agent")
st.markdown("### Interactive Command Center")

# --- PROACTIVE ALERT POLLING ---
try:
    alerts_res = requests.get(f"{BACKEND_URL}/alerts")
    if alerts_res.status_code == 200:
        alerts = alerts_res.json()
        
        if alerts:
            latest = alerts[-1]
            # Create unique ID for this specific alert event
            alert_unique_id = f"{latest['vehicle_id']}_{latest['timestamp']}"
            
            if alert_unique_id not in st.session_state.processed_alerts:
                
                # --- MEMORY SYNC ---
                # Adopt the backend's thread ID so the user joins the active session
                remote_thread_id = latest.get("thread_id")
                if remote_thread_id:
                    st.session_state.thread_id = remote_thread_id
                    st.toast(f"🔗 Connected to Agent Session: {remote_thread_id}")

                # Show notification
                st.toast(f"🚨 CRITICAL ALERT: {latest['vehicle_id']}", icon="🔥")
                
                # Inject Agent's opening message
                ai_opening_message = (
                    f"**⚠️ PROACTIVE ALERT**\n\n"
                    f"I have detected a critical anomaly on **{latest['vehicle_id']}**.\n"
                    f"**Analysis:** {latest['message']}\n\n"
                    "Would you like me to proceed with the recommended repair?"
                )
                
                st.session_state.messages.append({"role": "assistant", "content": ai_opening_message})
                st.session_state.processed_alerts.add(alert_unique_id)
                
except Exception as e:
    st.error(f"Polling Error: {e}")

# --- CHAT INTERFACE ---

# 1. Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 2. User Input Area
if prompt := st.chat_input("Type your response..."):
    # Add User message to UI
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Send to Backend Agent
    with st.spinner("Agent is coordinating..."):
        try:
            payload = {
                "message": prompt,
                "thread_id": st.session_state.thread_id,
                "vehicle_id": "Vehicle-123"
            }
            
            res = requests.post(f"{BACKEND_URL}/chat", json=payload)
            
            if res.status_code == 200:
                ai_response = res.json()["response"]
                
                # Add AI response to UI
                st.session_state.messages.append({"role": "assistant", "content": ai_response})
                with st.chat_message("assistant"):
                    st.markdown(ai_response)
            else:
                st.error(f"Error: {res.status_code}")
                
        except Exception as e:
            st.error(f"Connection Failed: {e}")

# --- AUTO-REFRESH ---
# Polls backend every 2 seconds
time.sleep(2)
st.rerun()