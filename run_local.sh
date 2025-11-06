
#!/usr/bin/env bash
# local non-docker run for convenience
python data/generate_synthetic.py
python models/train_tiny_audio_model.py
# start api app with uvicorn
uvicorn api.app:app --host 0.0.0.0 --port 8000 &
# start agents as background for demo
python agents/audio_health_agent.py &
python agents/master_agent.py &
python agents/diagnosis_agent.py &
python agents/customer_engagement_agent.py &
# open streamlit
streamlit run ui/streamlit_app.py --server.port 8501 --server.headless true
