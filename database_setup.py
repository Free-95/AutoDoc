import sqlite3
import random
from datetime import datetime, timedelta

DB_NAME = "fleet_data.db"

def init_db():
    print("🌱 Initializing Fleet Database...")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # --- 1. OPTIMIZATION: ENABLE WAL MODE ---
    cursor.execute("PRAGMA journal_mode=WAL;")

    # --- 2. RESET TABLES ---
    cursor.execute("DROP TABLE IF EXISTS vehicles")
    cursor.execute("DROP TABLE IF EXISTS maintenance_history")
    cursor.execute("DROP TABLE IF EXISTS capa_records")
    cursor.execute("DROP TABLE IF EXISTS appointments")

    # --- 3. CREATE SCHEMA ---
    
    # Vehicles Table (Live State)
    cursor.execute('''CREATE TABLE vehicles (
        vehicle_id TEXT PRIMARY KEY,
        model TEXT,
        engine_temp INTEGER,
        oil_life INTEGER,
        tire_pressure INTEGER,
        odometer INTEGER,
        error_code TEXT,
        status TEXT
    )''')

    # Maintenance History (Historical Records)
    cursor.execute('''CREATE TABLE maintenance_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id TEXT,
        service_date TEXT,
        service_type TEXT,
        description TEXT,
        cost INTEGER
    )''')

    # CAPA / RCA Records (Manufacturing Knowledge Base)
    cursor.execute('''CREATE TABLE capa_records (
        component TEXT,
        defect_type TEXT,
        action_required TEXT,
        batch_id TEXT
    )''')

    # Scheduler (Appointments)
    cursor.execute('''CREATE TABLE appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slot_time TEXT,
        is_booked BOOLEAN,
        booked_vehicle_id TEXT
    )''')

    # --- 4. SEED DATA ---
    
    # A. Vehicles (The 10 Specific Profiles)
    print("   ...Seeding 10 Vehicles...")
    vehicles = [
        ("Vehicle-123", "F-150", 115, 40, 32, 45000, "P0118", "Active"), # CRITICAL
        ("Vehicle-101", "Sedan", 90, 85, 35, 12000, "None", "Active"),
        ("Vehicle-102", "SUV", 92, 70, 34, 25000, "None", "Active"),
        ("Vehicle-103", "Truck", 95, 60, 30, 55000, "None", "Active"),
        ("Vehicle-104", "Sedan", 88, 90, 35, 5000, "None", "Active"),
        ("Vehicle-105", "Coupe", 105, 20, 31, 62000, "P0420", "Warning"), # WARNING
        ("Vehicle-106", "Van", 91, 55, 33, 30000, "None", "Active"),
        ("Vehicle-107", "SUV", 89, 80, 35, 15000, "None", "Active"),
        ("Vehicle-108", "Truck", 112, 10, 28, 85000, "P0118", "Critical"), # CRITICAL
        ("Vehicle-109", "Sedan", 90, 75, 34, 20000, "None", "Active"),
    ]
    cursor.executemany("INSERT INTO vehicles VALUES (?, ?, ?, ?, ?, ?, ?, ?)", vehicles)

    # B. Enhanced History Seeding (NEW SECTION)
    print("   ...Generating Procedural Maintenance History...")
    
    service_options = [
        ("Oil Change", "Standard synthetic oil change and filter replacement", 80),
        ("Tire Rotation", "Rotated tires and checked pressure", 40),
        ("Brake Inspection", "Visual inspection of pads and rotors", 50),
        ("Fluid Top-off", "Topped off coolant and wiper fluid", 30),
        ("Air Filter", "Replaced engine air intake filter", 45),
        ("Battery Check", "Voltage test and terminal cleaning", 25)
    ]

    history_records = []
    
    # 1. Add specific narrative history for our Critical Car (123)
    history_records.append(("Vehicle-123", "2024-01-10", "Oil Change", "Standard synthetic oil change", 80))
    history_records.append(("Vehicle-123", "2023-08-15", "Tire Rotation", "Rotated all 4 tires", 40))
    
    # 2. Add specific history for the other Critical Car (108)
    history_records.append(("Vehicle-108", "2024-02-01", "Brake Pad", "Replaced front brake pads", 200))

    # 3. Generate random history for EVERY vehicle to flesh out the DB
    today = datetime.now()
    all_vehicle_ids = [v[0] for v in vehicles]
    
    for vid in all_vehicle_ids:
        # Give each car 3 to 7 random past service events
        num_services = random.randint(3, 7)
        for _ in range(num_services):
            # Pick a random date in the last 2 years
            days_ago = random.randint(10, 700)
            service_date = (today - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            
            # Pick a random service type
            s_type, s_desc, s_cost = random.choice(service_options)
            
            history_records.append((vid, service_date, s_type, s_desc, s_cost))

    cursor.executemany("INSERT INTO maintenance_history (vehicle_id, service_date, service_type, description, cost) VALUES (?, ?, ?, ?, ?)", history_records)

    # C. CAPA Records
    capa = [
        ("Coolant Sensor", "Seal Failure", "Replace with Part #992-B (Upgraded Gasket)", "Batch-992"),
        ("Catalytic Converter", "Efficiency Below Threshold", "Check O2 Sensor first", "Batch-101"),
    ]
    cursor.executemany("INSERT INTO capa_records VALUES (?, ?, ?, ?)", capa)

    # D. Schedule Slots
    print("   ...Seeding Appointment Slots...")
    slots = []
    # Store strictly HH:MM 24-hour format
    for hour in [9, 10, 11, 13, 14, 15, 16]: 
        slot_time = f"{hour:02d}:00" 
        slots.append((slot_time, False, None))
    
    cursor.executemany("INSERT INTO appointments (slot_time, is_booked, booked_vehicle_id) VALUES (?, ?, ?)", slots)

    conn.commit()
    conn.close()
    print(f"✅ Database 'fleet_data.db' reset. Seeded {len(history_records)} historical records.")

if __name__ == "__main__":
    init_db()