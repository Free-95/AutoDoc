from fastapi import APIRouter
import requests
import random

router = APIRouter()

@router.post('/diagnose')
def diagnose(payload: dict):
    """
    Logic from agents/diagnosis_agent.py
    """
    vin = payload.get('vin','unknown')
    last_digit = 0
    for ch in vin[::-1]:
        if ch.isdigit():
            last_digit = int(ch); break
    
    # Use telemetry data for a more realistic rule
    # This is a placeholder; you can enhance this
    temp_trend = payload.get('sensors', {}).get('engine_temp_c', 80)
    
    risk = 0.8 if temp_trend > 95 else 0.2 # Simple rule
    
    return {
        'vin':vin,
        'risk':risk,
        'eta_days': 7 if risk > 0.5 else 30,
        'component': 'Thermostat' if risk > 0.5 else 'Battery',
        'explain':['engine_temp high'] if risk > 0.5 else ['routine check']
    }

@router.post('/engage')
def engage(payload: dict):
    """
    Logic from agents/customer_engagement_agent.py
    """
    vin = payload.get('vin')
    diag = payload.get('diag',{})
    audio_score = payload.get('audio_score',None)
    
    print(f"[Voice SIM] Hello owner of {vin}. Our system detected an issue: {diag.get('component')} risk {diag.get('risk')}. Audio score: {audio_score}")
    
    # Get slots and auto book first
    try:
        s = requests.get('http://localhost:8000/slots').json()
        if s:
            slot = s[0]
            r = requests.post(
                'http://localhost:8000/bookings', 
                params={'slot_id':slot['slot_id'],'vin':vin}
            )
            return {'status':'booked','slot':slot}
    except requests.exceptions.ConnectionError:
        print("[Engage Node] ERROR: Could not connect to scheduler API. Is API running?")
        return {'status':'error', 'msg': 'Scheduler API not reachable'}
        
    return {'status':'no_slots'}