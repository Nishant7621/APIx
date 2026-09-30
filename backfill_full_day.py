import sys
import datetime
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scheduler.daily_auto_collector import execute_hourly_ingestion_cycle
from database.connection import get_session_maker
from database.models import FareQuote, CollectionRun
from sqlalchemy import func

def backfill_day(target_date_str: str):
    target_date = datetime.date.fromisoformat(target_date_str)
    print("=" * 65)
    print(f"  APIx - Backfilling Complete 24-Hour Cycle for: {target_date}")
    print("=" * 65)

    created_hours = 0
    for hour in range(24):
        res = execute_hourly_ingestion_cycle(target_date=target_date, target_hour=hour, force=False)
        status = res.get("status")
        quotes = res.get("quotes_count", 0)
        if status == "SUCCESS":
            created_hours += 1
            print(f"  [Hour {hour:02d}:00] +{quotes} quotes created")
        else:
            print(f"  [Hour {hour:02d}:00] {res.get('message', 'Already exists')}")

    # Summary
    s = get_session_maker()()
    total_day_quotes = s.query(func.count(FareQuote.id)).filter(func.date(FareQuote.collected_at) == target_date).scalar()
    total_day_runs = s.query(CollectionRun).filter(func.date(CollectionRun.started_at) == target_date).count()
    total_db_quotes = s.query(func.count(FareQuote.id)).scalar()
    s.close()

    print("\n" + "=" * 65)
    print(f"  [COMPLETE] {target_date} now has:")
    print(f"  - Total Runs   : {total_day_runs} hourly runs")
    print(f"  - Total Quotes : {total_day_quotes:,} verified rows")
    print(f"  - Total DB Rows: {total_db_quotes:,} total quotes across all dates")
    print("=" * 65)

if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else "2026-09-29"
    backfill_day(date_arg)
