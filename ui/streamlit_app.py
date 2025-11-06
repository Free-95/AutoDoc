
import streamlit as st, pandas as pd, time, os, json
st.set_page_config(page_title='Agentic AI Ops (Audio+Telematics Demo)')
st.title('Agentic AI - Audio + Telematics Demo')

if os.path.exists('data/sample_vehicles.csv'):
    df = pd.read_csv('data/sample_vehicles.csv')
    st.dataframe(df)
else:
    st.info('Run data/generate_synthetic.py to create sample_vehicles.csv')

st.header('Incoming Audio')
in_dir = 'data/incoming_audio'
os.makedirs(in_dir, exist_ok=True)
files = os.listdir(in_dir)
st.write('Pending audio files:', files)

st.header('UEBA Audit (last 100 lines)')
if os.path.exists('data/ueba_audit.log'):
    with open('data/ueba_audit.log') as f:
        lines = f.readlines()[-100:]
    st.text('\n'.join(lines))
else:
    st.text('No audit log yet.')

st.header('Audio Events')
if os.path.exists('data/audio_events.jsonl'):
    with open('data/audio_events.jsonl') as f:
        lines = f.readlines()[-20:]
    items = [json.loads(l.strip()) for l in lines]
    st.json(items)
else:
    st.text('No audio events yet.')

st.markdown('**Demo tips**: Drop a small WAV file into `data/incoming_audio` to simulate a recorded sample.')
