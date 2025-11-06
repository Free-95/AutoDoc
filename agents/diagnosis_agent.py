
from fastapi import FastAPI
import random
app = FastAPI()

@app.post('/diagnose')
def diagnose(payload: dict):
    vin = payload.get('vin','unknown')
    last_digit = 0
    for ch in vin[::-1]:
        if ch.isdigit():
            last_digit = int(ch); break
    risk = 0.8 if last_digit % 2 == 0 else 0.2
    return {'vin':vin,'risk':risk,'eta_days':7 if risk>0.5 else 30,'component':'Thermostat' if risk>0.5 else 'Battery','explain':['engine_temp trend','fan_duty high']}
