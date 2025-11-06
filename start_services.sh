
#!/usr/bin/env bash
# Start combined FastAPI app (hosts multiple APIs and telematics WS)
uvicorn api.app:app --host 0.0.0.0 --port 8000 &
# Start telematics WS (served on same process via background thread in api.telematics)
# Start Streamlit UI
streamlit run ui/streamlit_app.py --server.port 8501 --server.headless true
