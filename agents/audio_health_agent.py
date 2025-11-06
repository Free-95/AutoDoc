
# This is a lightweight runnable stub that periodically scans incoming_audio and calls predictor
import time, os, requests, json
IN_DIR = 'data/incoming_audio'
os.makedirs(IN_DIR, exist_ok=True)

while True:
    files = [f for f in os.listdir(IN_DIR) if f.endswith('.wav')]
    for f in files:
        try:
            r = requests.post('http://localhost:8000/predict_audio_health', files={'file': open(os.path.join(IN_DIR,f),'rb')})
            res = r.json()
            score = res.get('health_score',1.0)
            print('Audio file', f, 'score', score)
            if score < 0.75:
                # notify master via simple file-based event for demo
                with open('data/audio_events.jsonl','a') as ev:
                    ev.write(json.dumps({'file':f,'score':score})+'\n')
            os.remove(os.path.join(IN_DIR,f))
        except Exception as e:
            print('error', e)
    time.sleep(3)
