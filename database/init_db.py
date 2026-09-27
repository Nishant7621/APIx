import sys
from pathlib import Path
from sqlalchemy import inspect

# Ensure root path is in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from database.connection import get_engine, Base
import database.models  # Ensure models are registered with Base.metadata

def init_database():
    """
    Creates all database tables defined in models.py.
    Safe to run repeatedly (uses CREATE TABLE IF NOT EXISTS).
    """
    print("=" * 60)
    print("  Initializing Airline Price Index (APIx) Database Schema")
    print("=" * 60)

    engine = get_engine()
    dialect_name = engine.dialect.name
    print(f"[INFO] Target Database Engine: {dialect_name.upper()}")

    print("[INFO] Creating tables from SQLAlchemy Base metadata...")
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    print("[SUCCESS] Found tables in database:")
    required_tables = ["collection_runs", "raw_responses", "fare_quotes", "source_health"]
    all_found = True
    for tbl in required_tables:
        status = "[OK] PRESENT" if tbl in existing_tables else "[X] MISSING"
        print(f"  - {tbl:<20} : {status}")
        if tbl not in existing_tables:
            all_found = False

    if all_found:
        print("\n[SUCCESS] All required APIx tables created and verified successfully!")
    else:
        print("\n[WARNING] Some tables were not detected. Please verify database permissions.")

if __name__ == "__main__":
    init_database()
