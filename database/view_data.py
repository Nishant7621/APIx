import sys
from pathlib import Path

# Ensure root directory is on sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from database.connection import get_session_maker
from database.models import FareQuote, CollectionRun, RawResponse
from sqlalchemy import func

def display_recent_data(limit=15):
    SessionLocal = get_session_maker()
    session = SessionLocal()

    total_quotes = session.query(FareQuote).count()
    total_runs = session.query(CollectionRun).count()
    total_raw = session.query(RawResponse).count()

    print("\n" + "=" * 95)
    print("                POSTGRESQL DATABASE AUDIT: apix_db -> fare_quotes")
    print("=" * 95)
    print(f"  Total Fare Quotes in DB : {total_quotes:,} rows")
    print(f"  Total Raw JSON Payloads : {total_raw:,} records")
    print(f"  Total Collection Runs   : {total_runs:,} runs")
    print("=" * 95)

    recent_quotes = session.query(FareQuote).order_by(FareQuote.id.desc()).limit(limit).all()

    header = f"{'ID':<7} | {'COLLECTED AT':<19} | {'PLATFORM':<15} | {'AIRLINE':<12} | {'ROUTE':<9} | {'HORIZON':<7} | {'TOTAL FARE':<10}"
    print(header)
    print("-" * 95)

    for q in recent_quotes:
        col_time = q.collected_at.strftime("%Y-%m-%d %H:%M:%S") if q.collected_at else "N/A"
        route = f"{q.origin}->{q.destination}"
        window = f"T+{q.advance_window_days}"
        fare = f"INR {q.total_fare:,.2f}" if q.total_fare else "N/A"
        print(f"{q.id:<7} | {col_time:<19} | {q.source_name[:15]:<15} | {q.airline_name[:12]:<12} | {route:<9} | {window:<7} | {fare:<14}")

    print("-" * 95)
    print(f"Showing the latest {len(recent_quotes)} rows from PostgreSQL 18 table 'fare_quotes'.")
    print("=" * 95 + "\n")

def display_raw_data(limit=5):
    SessionLocal = get_session_maker()
    session = SessionLocal()

    total_raw = session.query(RawResponse).count()

    print("\n" + "=" * 95)
    print("            POSTGRESQL AUDIT: apix_db -> raw_responses (RAW PAYLOADS)")
    print("=" * 95)
    print(f"  Total Raw Responses Stored: {total_raw:,} records with SHA-256 Hashes")
    print("=" * 95)

    recent_raw = session.query(RawResponse).order_by(RawResponse.id.desc()).limit(limit).all()

    for r in recent_raw:
        col_time = r.collected_at.strftime("%Y-%m-%d %H:%M:%S") if r.collected_at else "N/A"
        print(f"Record ID    : {r.id}")
        print(f"Timestamp    : {col_time}")
        print(f"Sector       : {r.origin} -> {r.destination} (Travel: {r.travel_date}, Window: T+{r.advance_window_days})")
        print(f"Source       : {r.source_name}")
        print(f"SHA-256 Hash : {r.payload_hash}")
        preview = r.payload_json[:220] + "..." if r.payload_json and len(r.payload_json) > 220 else (r.payload_json or "{}")
        print(f"Raw JSON     : {preview}")
        print("-" * 95)

if __name__ == "__main__":
    if "--raw" in sys.argv:
        display_raw_data(5)
    else:
        limit = 15
        for arg in sys.argv[1:]:
            if arg.isdigit():
                limit = int(arg)
        display_recent_data(limit)
