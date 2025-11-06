
import time, json, requests, os
UEBA_LOG = 'data/ueba_audit.log'

def ueba_before(agent, action, payload):
    # simple block if payload contains "BLOCK_ME" (demo)
    if payload.get('force_block'):
        with open(UEBA_LOG,'a') as f:
            f.write(json.dumps({'agent':agent,'action':action,'decision':'block'})+'\n')
        return {'action':'block','reason':'forced'}
    with open(UEBA_LOG,'a') as f:
        f.write(json.dumps({'agent':agent,'action':action,'decision':'allow'})+'\n')
    return {'action':'allow'}

def process_tick(tick):
    # call diagnosis agent (local endpoint)
    try:
        resp = requests.post('http://localhost:8000/diagnose', json={'vin':tick['vin']}, timeout=5)
        diag = resp.json()
    except Exception as e:
        diag = {'vin':tick['vin'],'risk':0.1}
    # if acoustic file exists, call audio predictor
    incoming = 'data/incoming_audio'
    if os.path.exists(incoming):
        for f in os.listdir(incoming):
            if f.endswith('.wav'):
                try:
                    pr = requests.post('http://localhost:8000/predict_audio_health', files={'file': open(os.path.join(incoming,f),'rb')})
                    score = pr.json().get('health_score',1.0)
                    print('Audio health score', score)
                    if score < 0.75:
                        # engage customer
                        requests.post('http://localhost:8000/engage', json={'vin':tick['vin'],'diag':diag,'audio_score':score})
                        os.remove(os.path.join(incoming,f))
                except Exception as e:
                    print('audio predict error', e)

if __name__=='__main__':
    print('Master agent reading telematics queue...')
    qpath = 'data/telematics_queue.jsonl'
    # ensure file exists
    open(qpath,'a').close()
    seen = 0
    while True:
        with open(qpath) as q:
            lines = q.readlines()
        if len(lines) > seen:
            for line in lines[seen:]:
                try:
                    tick = json.loads(line.strip())
                    dec = ueba_before('master','ingest',tick)
                    if dec['action']=='allow':
                        process_tick(tick)
                except:
                    pass
            seen = len(lines)
        time.sleep(1)
