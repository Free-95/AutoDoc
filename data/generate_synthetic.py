
import csv, random, os
from datetime import datetime, timedelta
os.makedirs('data', exist_ok=True)
models = ['Sedan-A','SUV-B','Compact-C','EV-X','Hatch-D']
usage_patterns = ['city','highway','mixed','rideshare','delivery']

def gen_vin(i):
    return f"MH12AB{i:04d}"

rows = []
for i in range(1,11):
    vin = gen_vin(i)
    model = random.choice(models)
    usage = random.choice(usage_patterns)
    mileage = random.randint(8000,150000)
    last_service = (datetime.now() - timedelta(days=random.randint(10,400))).strftime('%Y-%m-%d')
    dtc = random.choice(['None','P0128','P0420','P0300'])
    rows.append({
        'vin': vin,
        'model': model,
        'usage': usage,
        'mileage_km': mileage,
        'last_service': last_service,
        'dtc': dtc
    })

with open('data/sample_vehicles.csv','w',newline='') as f:
    writer = csv.DictWriter(f,fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print('written data/sample_vehicles.csv')
