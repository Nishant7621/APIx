import sys
from pathlib import Path

# Ensure root directory is on sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from collector.example_adapter import ExamplePermittedAdapter
from database.connection import get_session_maker
from database.models import FareQuote

def run_sample_collection():
    """
    Executes a single test collection run for route DEL-BOM at window T+7.
    """
    print("=" * 65)
    print("  APIx Single Route Collection: DEL -> BOM (Window: T+7)")
    print("=" * 65)

    adapter = ExamplePermittedAdapter()
    result = adapter.collect(origin="DEL", destination="BOM", advance_window_days=7)

    print(f"\n[INFO] Collection Run ID   : {result['run_id']}")
    print(f"[INFO] Run Status          : {result['status']}")
    print(f"[INFO] Raw Response ID     : {result.get('raw_response_id')}")
    print(f"[INFO] Payload SHA-256     : {result.get('payload_hash')}")
    print(f"[INFO] Quotes Stored       : {result.get('records_collected')}")

    # Inspect stored quotes
    SessionLocal = get_session_maker()
    session = SessionLocal()
    try:
        quotes = session.query(FareQuote).filter_by(collection_run_id=result["run_id"]).all()
        print("\n[EXTRACTED NORMALIZED FARE QUOTES]:")
        print("-" * 65)
        for q in quotes:
            flight_type = "Direct" if q.stop_count == 0 else f"{q.stop_count}-Stop"
            print(
                f"  [{q.airline_code}] {q.flight_number:<8} | {flight_type:<8} | "
                f"Base: INR {q.base_fare:>7.2f} + Tax: INR {q.taxes:>6.2f} = Total: INR {q.total_fare:>7.2f}"
            )
        print("-" * 65)
        print("[SUCCESS] Phase 2 single-route adapter run completed successfully!\n")
    finally:
        session.close()

if __name__ == "__main__":
    run_sample_collection()
