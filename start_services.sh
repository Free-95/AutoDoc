#!/usr/bin/env bash

# Start combined FastAPI app (hosts multiple APIs and telematics WS)
uvicorn api.app:app --host 0.0.0.0 --port 8000 &

# Wait for API to be up before starting agents
echo "Waiting for API server to start..."
sleep 5

echo "Starting Audio Health Agent..."
python agents/audio_health_agent.py &

echo "Starting Master Agent (Orchestrator)..."
python agents/master_agent.py &

# Start Streamlit UI
echo "Starting Streamlit UI..."
streamlit run ui/streamlit_app.py --server.port 8501 --server.headless true