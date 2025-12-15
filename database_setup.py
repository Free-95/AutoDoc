# database_setup.py
import sqlite3
import random
from datetime import datetime, timedelta

DB_NAME = "fleet_data.db"

def init_db():
    print("🌱 Initializing Fleet Database...")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # --- 1. OPTIMIZATION: ENABLE WAL MODE ---
    # This is crucial for handling simultaneous reads (Agent) and writes (Simulation)
    # without hitting "Database Locked" errors.
    cursor.execute("PRAGMA journal_mode=WAL;")

    # --- 2. RESET TABLES (Start Fresh) ---
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

    # History
    history = [
        ("Vehicle-123", "2024-01-10", "Oil Change", "Standard synthetic oil change", 80),
        ("Vehicle-123", "2023-08-15", "Tire Rotation", "Rotated all 4 tires", 40),
        ("Vehicle-108", "2024-02-01", "Brake Pad", "Replaced front brake pads", 200),
    ]
    cursor.executemany("INSERT INTO maintenance_history (vehicle_id, service_date, service_type, description, cost) VALUES (?, ?, ?, ?, ?)", history)

    # CAPA Records
    capa = [
        ("Coolant Sensor", "Seal Failure", "Replace with Part #992-B (Upgraded Gasket)", "Batch-992"),
        ("Catalytic Converter", "Efficiency Below Threshold", "Check O2 Sensor first", "Batch-101"),
    ]
    cursor.executemany("INSERT INTO capa_records VALUES (?, ?, ?, ?)", capa)

    # Schedule Slots (Next 3 Days)
    # Storing simpler HH:MM format for reliable AI matching
    print("   ...Seeding Appointment Slots...")
    slots = []
    
    # Create slots for tomorrow
    base_date = datetime.now() + timedelta(days=1)
    date_str = base_date.strftime("%Y-%m-%d") # Store date separately if needed, but for now we mix
    
    # We will store strictly HH:MM 24-hour format (09:00, 14:00) 
    # to match the normalize logic in agents.py
    for hour in [9, 10, 11, 13, 14, 15, 16]: 
        slot_time = f"{hour:02d}:00" 
        slots.append((slot_time, False, None))
    
    cursor.executemany("INSERT INTO appointments (slot_time, is_booked, booked_vehicle_id) VALUES (?, ?, ?)", slots)

    conn.commit()
    conn.close()
    print("✅ Database 'fleet_data.db' reset and seeded successfully.")

if __name__ == "__main__":
    init_db()