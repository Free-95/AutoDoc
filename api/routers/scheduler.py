
from fastapi import APIRouter
import datetime, uuid
router = APIRouter()

centers = {'PUN-MET-01':{'bays':4,'skills':['engine','battery','thermal']}, 'BLR-CEN-01':{'bays':3,'skills':['engine','electrical']}}
slots = []
bookings = {}

start = datetime.datetime.now().replace(hour=9,minute=0,second=0,microsecond=0)
for c in centers:
    for d in range(1,8):
        for h in [9,11,14,16]:
            s = start + datetime.timedelta(days=d) + datetime.timedelta(hours=(h-start.hour))
            slots.append({'slot_id':str(uuid.uuid4()),'center_id':c,'start':s.isoformat(),'dur_min':90,'skill':'engine','available':True})

@router.get('/centers')
def get_centers():
    return centers

@router.get('/slots')
def get_slots(center_id: str = None):
    if center_id:
        return [s for s in slots if s['center_id']==center_id and s['available']]
    return [s for s in slots if s['available']]

@router.post('/bookings')
def book(slot_id: str, vin: str):
    for s in slots:
        if s['slot_id']==slot_id and s['available']:
            s['available']=False
            booking_id = str(uuid.uuid4())
            bookings[booking_id] = {'booking_id':booking_id,'slot':s,'vin':vin}
            return {'status':'ok','booking_id':booking_id,'slot':s}
    return {'status':'error','msg':'slot not available'}
