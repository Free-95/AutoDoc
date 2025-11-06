
from fastapi import APIRouter
import asyncio, json, random, csv, os
from websockets import serve
from datetime import datetime
router = APIRouter()

# telematics emitter as background async task; clients can connect to ws://host:8765 if exposed separately
VEHICLES_CSV = 'data/sample_vehicles.csv'
vehicles = []
if os.path.exists(VEHICLES_CSV):
    with open(VEHICLES_CSV) as f:
        import csv
        reader = csv.DictReader(f)
        for r in reader:
            vehicles.append(r)
else:
    # synthetic fallback
    for i in range(1,6):
        vehicles.append({'vin':f'MH12AB{i:04d}','dtc':'None','mileage_km':10000})

async def start_telematics():
    # this coroutine emits ticks into a simple in-memory "event" bus for demo
    while True:
        for v in vehicles:
            tick = {
                'vin': v['vin'],
                'ts': datetime.utcnow().isoformat() + 'Z',
                'sensors': {
                    'engine_temp_c': round(80 + random.gauss(0,5) + (1 if v.get('dtc','None')!='None' else 0)*10,2),
                    'battery_v': round(12.5 + random.gauss(0,0.3),2),
                    'vibration_rms': round(abs(random.gauss(0.5,0.8)),2),
                    'fan_duty': round(min(1.0, max(0, random.gauss(0.2,0.25) + (1 if v.get('dtc','None')=='P0128' else 0)*0.6)),2)
                },
                'odometer_km': int(v.get('mileage_km',0)) + random.randint(0,5)
            }
            # write to a file queue for agents to read (simple IPC for demo)
            with open('data/telematics_queue.jsonl','a') as q:
                q.write(json.dumps(tick) + '\n')
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.5)
