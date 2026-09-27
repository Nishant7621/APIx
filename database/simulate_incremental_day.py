import sys
import datetime
import random
from pathlib import Path

# Ensure root directory is on sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from database.connection import get_session_maker
from database.models import CollectionRun, RawResponse, FareQuote, SourceHealth, utc_now
from database.seed_demo_data import (
    PILOT_ROUTES,
    PILOT_WINDOWS,
    AIRLINES,
    ROUTE_BASE_PRICES,
    WINDOW_MULTIPLIERS,
    generate_payload_hash
)

def add_fresh_incremental_day(day_label: str = "Today's Fresh Live Collection"):
    """
    Simulates a fresh incremental collection run for today (Day 31+).
    Demonstrates incremental time-series appending without overwriting past history.
    """
    print("=" * 65)
    print(f"  APIx - Ingesting Fresh Incremental Day: {day_label}")
    print("=" * 65)

    SessionLocal = get_session_maker()
    session = SessionLocal()

    try:
        # Determine latest collection run date in DB
        latest_quote = session.query(FareQuote).order_by(FareQuote.collected_at.desc()).first()
        if latest_quote and latest_quote.collected_at:
            next_collection_date = latest_quote.collected_at + datetime.timedelta(days=1)
        else:
            next_collection_date = utc_now()

        # 1. Create fresh CollectionRun
        run = CollectionRun(
            source_name="PERMITTED_LIVE_FEED",
            scheduled_at=next_collection_date,
            started_at=next_collection_date,
            completed_at=next_collection_date + datetime.timedelta(seconds=22),
            status="SUCCESS",
            records_collected=0,
            duration_seconds=22.45
        )
        session.add(run)
        session.flush()

        quotes_count = 0
        responses_count = 0

        # Simulate slight market price movement (+2% to +5% inflation today)
        market_inflation_factor = 1.035

        for origin, dest, orig_city, dest_city in PILOT_ROUTES:
            base_route_price = ROUTE_BASE_PRICES.get((origin, dest), 4500.0)

            for window in PILOT_WINDOWS:
                travel_date = (next_collection_date + datetime.timedelta(days=window)).date()
                window_mult = WINDOW_MULTIPLIERS.get(window, 1.0)

                mock_raw_items = []
                for airline in AIRLINES:
                    f_num = f"{airline['flight_prefix']}{random.randint(200, 999)}"
                    dep_hour = random.randint(6, 21)
                    dep_time = datetime.datetime.combine(travel_date, datetime.time(dep_hour, 0))
                    arr_time = dep_time + datetime.timedelta(hours=2, minutes=15)

                    calc_total = base_route_price * window_mult * market_inflation_factor * random.uniform(0.98, 1.04)
                    b_fare = round(calc_total * 0.70, 2)
                    tax = round(calc_total * 0.22, 2)
                    charges = round(calc_total - (b_fare + tax), 2)
                    t_fare = round(b_fare + tax + charges, 2)

                    mock_raw_items.append({
                        "flight_number": f_num,
                        "airline_code": airline["code"],
                        "airline_name": airline["name"],
                        "stop_count": 0,
                        "dep_time": dep_time.isoformat(),
                        "arr_time": arr_time.isoformat(),
                        "base_fare": b_fare,
                        "taxes": tax,
                        "mandatory_charges": charges,
                        "total_fare": t_fare,
                        "currency": "INR",
                        "fare_class": "ECONOMY"
                    })

                # Store RawResponse
                raw_payload = {
                    "source": "PERMITTED_LIVE_FEED",
                    "origin": origin,
                    "destination": dest,
                    "travel_date": str(travel_date),
                    "advance_window_days": window,
                    "quotes": mock_raw_items
                }
                p_hash = generate_payload_hash(raw_payload)

                raw_resp = RawResponse(
                    collection_run_id=run.id,
                    source_name="PERMITTED_LIVE_FEED",
                    collected_at=next_collection_date,
                    origin=origin,
                    destination=dest,
                    travel_date=travel_date,
                    advance_window_days=window,
                    payload_json=str(raw_payload),
                    payload_hash=p_hash,
                    raw_content_type="application/json"
                )
                session.add(raw_resp)
                session.flush()
                responses_count += 1

                # Store FareQuotes across OTAs and Airline Portals
                ota_list = [
                    {"name": "MakeMyTrip", "type": "OTA", "fee": 350.0, "mult": 1.018},
                    {"name": "EaseMyTrip", "type": "OTA", "fee": 0.0, "mult": 0.992},
                    {"name": "Yatra", "type": "OTA", "fee": 299.0, "mult": 1.008},
                    {"name": "Cleartrip", "type": "OTA", "fee": 325.0, "mult": 1.012},
                    {"name": "Ixigo", "type": "OTA", "fee": 270.0, "mult": 1.003},
                    {"name": "Direct Airline Portal", "type": "AIRLINE_PORTAL", "fee": 0.0, "mult": 1.000},
                ]

                for idx, item in enumerate(mock_raw_items):
                    ota = ota_list[idx % len(ota_list)]
                    adjusted_base = round(item["base_fare"] * ota["mult"], 2)
                    adjusted_fee = ota["fee"]
                    adjusted_total = round(adjusted_base + item["taxes"] + adjusted_fee, 2)

                    quote = FareQuote(
                        collection_run_id=run.id,
                        source_name=ota["name"],
                        source_type=ota["type"],
                        collected_at=next_collection_date,
                        origin=origin,
                        destination=dest,
                        travel_date=travel_date,
                        advance_window_days=window,
                        airline_code=item["airline_code"],
                        airline_name=item["airline_name"],
                        flight_number=item["flight_number"],
                        departure_time=datetime.datetime.fromisoformat(item["dep_time"]),
                        arrival_time=datetime.datetime.fromisoformat(item["arr_time"]),
                        stop_count=0,
                        fare_class="ECONOMY",
                        base_fare=adjusted_base,
                        taxes=item["taxes"],
                        mandatory_charges=adjusted_fee,
                        total_fare=adjusted_total,
                        currency="INR",
                        availability_status="AVAILABLE",
                        raw_response_id=raw_resp.id,
                        duplicate_flag=False,
                        outlier_flag=False,
                        validation_notes=f"Incremental feed quote from {ota['name']}"
                    )
                    session.add(quote)
                    quotes_count += 1

        run.records_collected = quotes_count

        # Update source health
        health = session.query(SourceHealth).filter_by(source_name="PERMITTED_LIVE_FEED").first()
        if not health:
            health = SourceHealth(
                source_name="PERMITTED_LIVE_FEED",
                checked_at=utc_now(),
                status="HEALTHY",
                success_rate=100.0,
                average_response_time=1.05
            )
            session.add(health)
        health.last_successful_collection = utc_now()
        health.checked_at = utc_now()

        session.commit()
        print(f"[SUCCESS] Ingested 1 fresh daily collection run (ID: {run.id}).")
        print(f"[SUCCESS] Added {responses_count} raw responses and {quotes_count} new quotes.")
        print(f"[SUCCESS] Historical baseline data preserved completely.")

    finally:
        session.close()

if __name__ == "__main__":
    add_fresh_incremental_day()
