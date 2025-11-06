
from fastapi import APIRouter, File, UploadFile, HTTPException
import librosa, numpy as np, os, tensorflow as tf
router = APIRouter()

MODEL_PATH = 'models/vehicle_audio_health.h5'
# load a tiny placeholder model if exists; else provide mock predict
if os.path.exists(MODEL_PATH):
    model = tf.keras.models.load_model(MODEL_PATH)
else:
    model = None

@router.post('/predict_audio_health')
async def predict_audio_health(file: UploadFile = File(...)):
    data = await file.read()
    import io, soundfile as sf
    try:
        audio, sr = sf.read(io.BytesIO(data), dtype='float32')
    except Exception as e:
        raise HTTPException(status_code=400, detail='Invalid audio file')
    # rudimentary feature: energy & spectral centroid -> mock scoring
    if model is None:
        # compute simple heuristic
        import numpy as np
        energy = float((audio**2).mean())
        score = max(0.0, min(1.0, 1.0 - energy*100))
        return {'health_score': score, 'method':'heuristic'}
    else:
        # preprocess to mel spectrogram
        y = librosa.resample(audio.astype(float), orig_sr=sr, target_sr=16000)
        mel = librosa.feature.melspectrogram(y=y, sr=16000)
        mel_db = librosa.power_to_db(mel, ref=np.max)
        mel_db = np.expand_dims(mel_db, axis=(0, -1))
        health_score = float(model.predict(mel_db)[0][0])
        return {'health_score': health_score, 'method':'model'}
