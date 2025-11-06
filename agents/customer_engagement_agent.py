
from fastapi import FastAPI
import requests
app = FastAPI()

@app.post('/engage')
def engage(payload: dict):
    vin = payload.get('vin')
    diag = payload.get('diag',{})
    audio_score = payload.get('audio_score',None)
    # Simulate voice dialog by printing to console and auto-confirming a slot
    print(f"[Voice] Hello owner of {vin}. Our system detected an issue: {diag.get('component')} risk {diag.get('risk')}. Audio score: {audio_score}")
    # get slots and auto book first
    s = requests.get('http://localhost:8000/slots').json()
    if s:
        slot = s[0]
        r = requests.post('http://localhost:8000/bookings', params={'slot_id':slot['slot_id'],'vin':vin})
        return {'status':'booked','slot':slot}
    return {'status':'no_slots'}
