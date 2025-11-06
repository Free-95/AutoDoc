
import numpy as np, soundfile as sf, time, os, requests
OUT_DIR = 'data/incoming_audio'
os.makedirs(OUT_DIR, exist_ok=True)
SERVER = 'http://localhost:8000/upload_audio'

def make_tone(filename, sr=16000, duration=3.0, freq=200.0, amplitude=0.1):
    t = np.linspace(0, duration, int(sr*duration), endpoint=False)
    data = amplitude * np.sin(2*np.pi*freq*t)
    # add small random noise
    data += 0.01 * np.random.randn(len(data))
    sf.write(filename, data, samplerate=sr)
    return filename

if __name__ == '__main__':
    # create one normal and one faulty tone for demo
    n1 = 'data/incoming_audio/normal_engine.wav'
    n2 = 'data/incoming_audio/bearing_fault.wav'
    make_tone(n1, freq=180.0, amplitude=0.05)
    make_tone(n2, freq=600.0, amplitude=0.15)
    print('WAV files created in data/incoming_audio. You can upload them to the API or let agents pick them up.')
