import streamlit as st, pandas as pd, time, os, json

st.set_page_config(page_title='Agentic AI Ops (Audio+Telematics Demo)')
st.title('Agentic AI - Audio + Telematics Demo')

# --- Track the last seen block event ---
if 'last_block_ts' not in st.session_state:
    st.session_state.last_block_ts = None

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
    
    # --- START: POP-UP LOGIC ---
    if lines:
        try:
            # Check the most recent log entry
            last_line = lines[-1]
            last_event = json.loads(last_line.strip())
            
            # Check if it's a block event and if we haven't already shown it
            if (last_event.get('decision') == 'block' and 
                last_event.get('timestamp') != st.session_state.last_block_ts):
                
                # Show the pop-up toast
                st.toast(f"🚨 UEBA BLOCK: {last_event.get('reason')}", icon="🛡️")
                
                # Remember this event so we don't show it again
                st.session_state.last_block_ts = last_event.get('timestamp')
        except json.JSONDecodeError:
            pass # Ignore malformed lines
    # --- END: POP-UP LOGIC ---
        
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

# Add a simple auto-refresh to catch the event
time.sleep(2)

# Change st.rerun() to st.experimental_rerun() for streamlit v1.25.0
st.experimental_rerun()