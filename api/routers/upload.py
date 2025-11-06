
from fastapi import APIRouter, File, UploadFile
import os, shutil
router = APIRouter()
UPLOAD_DIR = 'data/incoming_audio'
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post('/upload_audio')
async def upload_audio(file: UploadFile = File(...)):
    path = os.path.join(UPLOAD_DIR, file.filename)
    with open(path, 'wb') as f:
        shutil.copyfileobj(file.file, f)
    return {'status':'received', 'path': path}
