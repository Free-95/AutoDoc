
# Agentic AI Predictive Maintenance - LangGraph Dockerized Scaffold

This scaffold provides a demo-ready environment with:
- Telematics WS (simulated)
- Single FastAPI app hosting: upload_audio, audio_predictor, scheduler_api, maintenance_api, worker endpoints
- Simple LangGraph-style Master Agent skeleton and Worker agents (Python stubs)
- Audio sensor stub and a tiny audio model trainer script
- Streamlit UI for demo visualization

Run with Docker Compose (recommended):
```bash
docker compose build
docker compose up
```

The app will expose:
- API: http://localhost:8000/
- Streamlit UI: http://localhost:8501/

Notes:
- `langgraph` package is included as placeholder in requirements.txt; adapt to actual package per your setup.
- Models are toy placeholders. Replace `models/vehicle_audio_health.h5` with a real trained model for production.
