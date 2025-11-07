import time
import json
import os
from agents.orchestrator import run_graph # Import the graph runner

if __name__ == '__main__':
    print('Master Agent (LangGraph Orchestrator) reading telematics queue...')
    qpath = 'data/telematics_queue.jsonl'
    
    # Ensure file exists
    os.makedirs('data', exist_ok=True)
    open(qpath, 'a').close()
    
    seen = 0
    while True:
        try:
            with open(qpath) as q:
                lines = q.readlines()
            
            if len(lines) > seen:
                new_lines = lines[seen:]
                for line in new_lines:
                    try:
                        tick = json.loads(line.strip())
                        print(f"\n--- [Master] Processing VIN: {tick.get('vin')} ---")
                        
                        # This one line now triggers the ENTIRE agentic workflow
                        run_graph(tick)
                        
                        print(f"--- [Master] Completed VIN: {tick.get('vin')} ---")
                    except json.JSONDecodeError:
                        print(f"Skipping malformed line: {line.strip()}")
                    except Exception as e:
                        print(f"Error processing tick: {e}")
                
                seen = len(lines)
            
            time.sleep(1) # Poll the file every second
            
        except FileNotFoundError:
            print("Telematics queue file not found, re-checking...")
            time.sleep(5)
        except Exception as e:
            print(f"An unexpected error occurred in master_agent: {e}")
            time.sleep(5)