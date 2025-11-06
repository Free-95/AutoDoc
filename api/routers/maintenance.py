
from fastapi import APIRouter
from pydantic import BaseModel
router = APIRouter()

jobs = []

class Job(BaseModel):
    vin: str
    job_date: str
    job_type: str
    parts: list
    cost: float
    dtc: str = 'None'

@router.get('/vehicles/{vin}/history')
def get_history(vin: str):
    return [j for j in jobs if j['vin']==vin]

@router.post('/vehicles/{vin}/jobcard')
def create_job(vin: str, job: Job):
    rec = job.dict()
    jobs.append(rec)
    return {'status':'ok','job':rec}
