import sys
import json
import hashlib
import random
import datetime
from pathlib import Path

# Ensure root directory in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from database.connection import get_session_maker
from database.models import CollectionRun, RawResponse, FareQuote, SourceHealth

# ==============================================================================
# Fixed Pilot Rules & Parameters
# ==============================================================================
PILOT_ROUTES = [
    ("DEL", "BOM", "Delhi", "Mumbai"),
    ("DEL", "BLR", "Delhi", "Bengaluru"),
    ("BOM", "BLR", "Mumbai", "Bengaluru"),
    ("DEL", "CCU", "Delhi", "Kolkata"),
    ("BLR", "HYD", "Bengaluru", "Hyderabad"),
    ("MAA", "DEL", "Chennai", "Delhi"),
]

PILOT_WINDOWS = [1, 7, 15, 30, 45]  # T+1, T+7, T+15, T+30, T+45

AIRLINES = [
    {"code": "6E", "name": "IndiGo", "flight_prefix": "6E-"},
    {"code": "AI", "name": "Air India", "flight_prefix": "AI-"},
    {"code": "QP", "name": "Akasa Air", "flight_prefix": "QP-"},
    {"code": "SG", "name": "SpiceJet", "flight_prefix": "SG-"},
]

# Base price anchor by route for realistic price variations (Economy, INR)
ROUTE_BASE_PRICES = {
    ("DEL", "BOM"): 4500.0,
    ("DEL", "BLR"): 5500.0,
    ("BOM", "BLR"): 3800.0,
    ("DEL", "CCU"): 4800.0,
    ("BLR", "HYD"): 3200.0,
    ("MAA", "DEL"): 5200.0,
}

# Advance booking curve multiplier: T+1 is highest, T+45 is lowest
WINDOW_MULTIPLIERS = {
    1: 1.55,   # Last minute premium
    7: 1.25,   # High demand
    15: 1.05,  # Moderate demand
    30: 0.95,  # Early bird
    45: 0.88,  # Advance purchase
}

def generate_payload_hash(data: dict) -> str:
    """Computes SHA-256 hash of payload dictionary for deduplication."""
    serialized = json.dumps(data, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

def seed_demo_data(days_back: int = 30, quotes_per_flight: int = 2):
    """
    Generates synthetic demo and historical replay data adhering strictly to the Pilot Rules.
    Clearly labeled with source_type='DEMO' and validation_notes for auditability.
    """
    SessionLocal = get_session_maker()
    session = SessionLocal()

    print("=" * 60)
    print(f"  Generating {days_back} Days of Pilot Demo Data")
    print("=" * 60)

    try:
        # Check if demo data already exists
        existing_demo_runs = session.query(CollectionRun).filter_by(source_name="DEMO_REPLAY_FEED").count()
        if existing_demo_runs > 0:
            print(f"[INFO] Found {existing_demo_runs} existing demo runs. Cleaning up previous demo data...")
            # Delete old demo runs (cascades to raw_responses and fare_quotes)
            session.query(CollectionRun).filter_by(source_name="DEMO_REPLAY_FEED").delete()
            session.query(SourceHealth).filter_by(source_name="DEMO_REPLAY_FEED").delete()
            session.commit()
            print("[INFO] Cleanup complete. Seeding fresh dataset...")

        now = datetime.datetime.now(datetime.timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0)
        total_quotes = 0
        total_responses = 0

        # Seed day by day
        for day_offset in range(days_back, -1, -1):
            collection_date = now - datetime.timedelta(days=day_offset)

            # 1. Create CollectionRun
            run = CollectionRun(
                source_name="DEMO_REPLAY_FEED",
                scheduled_at=collection_date,
                started_at=collection_date,
                completed_at=collection_date + datetime.timedelta(seconds=random.randint(15, 35)),
                status="SUCCESS",
                records_collected=0,
                duration_seconds=round(random.uniform(15.0, 35.0), 2),
            )
            session.add(run)
            session.flush()  # assign run.id

            run_quotes_count = 0

            # 2. Iterate across Pilot Routes and Booking Windows
            for origin, dest, orig_city, dest_city in PILOT_ROUTES:
                base_route_price = ROUTE_BASE_PRICES.get((origin, dest), 4500.0)

                for window in PILOT_WINDOWS:
                    travel_date = (collection_date + datetime.timedelta(days=window)).date()
                    window_mult = WINDOW_MULTIPLIERS.get(window, 1.0)

                    # Mock Raw Response payload
                    mock_raw_items = []
                    
                    # Generate Direct and Connecting flights for each airline
                    for airline in AIRLINES:
                        # Flight 1: Direct flight (stop_count = 0)
                        f_num_direct = f"{airline['flight_prefix']}{random.randint(100, 999)}"
                        dep_hour = random.randint(6, 21)
                        dep_time = datetime.datetime.combine(travel_date, datetime.time(dep_hour, random.choice([0, 15, 30, 45])))
                        arr_time = dep_time + datetime.timedelta(hours=random.randint(2, 3), minutes=random.randint(10, 40))

                        # Price calculation with slight daily variance
                        day_noise = 1.0 + random.uniform(-0.06, 0.06)
                        calc_total = base_route_price * window_mult * day_noise
                        # Consistent fare components
                        base_fare = round(calc_total * 0.70, 2)
                        taxes = round(calc_total * 0.22, 2)
                        mandatory_charges = round(calc_total - (base_fare + taxes), 2)
                        total_fare = round(base_fare + taxes + mandatory_charges, 2)

                        item_direct = {
                            "flight_number": f_num_direct,
                            "airline_code": airline["code"],
                            "airline_name": airline["name"],
                            "stop_count": 0,
                            "dep_time": dep_time.isoformat(),
                            "arr_time": arr_time.isoformat(),
                            "base_fare": base_fare,
                            "taxes": taxes,
                            "mandatory_charges": mandatory_charges,
                            "total_fare": total_fare,
                            "currency": "INR",
                            "fare_class": "ECONOMY"
                        }
                        mock_raw_items.append(item_direct)

                        # Flight 2: Connecting flight (stop_count = 1)
                        f_num_conn = f"{airline['flight_prefix']}{random.randint(1000, 1999)}"
                        conn_dep_hour = random.randint(6, 18)
                        conn_dep = datetime.datetime.combine(travel_date, datetime.time(conn_dep_hour, random.choice([10, 25, 40, 50])))
                        conn_arr = conn_dep + datetime.timedelta(hours=random.randint(4, 7), minutes=random.randint(15, 45))

                        # Connecting is slightly cheaper or has different pricing
                        conn_calc_total = calc_total * random.uniform(0.92, 1.04)
                        c_base = round(conn_calc_total * 0.68, 2)
                        c_taxes = round(conn_calc_total * 0.24, 2)
                        c_charges = round(conn_calc_total - (c_base + c_taxes), 2)
                        c_total = round(c_base + c_taxes + c_charges, 2)

                        item_conn = {
                            "flight_number": f_num_conn,
                            "airline_code": airline["code"],
                            "airline_name": airline["name"],
                            "stop_count": 1,
                            "dep_time": conn_dep.isoformat(),
                            "arr_time": conn_arr.isoformat(),
                            "base_fare": c_base,
                            "taxes": c_taxes,
                            "mandatory_charges": c_charges,
                            "total_fare": c_total,
                            "currency": "INR",
                            "fare_class": "ECONOMY"
                        }
                        mock_raw_items.append(item_conn)

                    # Create RawResponse record
                    raw_payload = {
                        "origin": origin,
                        "destination": dest,
                        "travel_date": str(travel_date),
                        "advance_window_days": window,
                        "passenger_count": 1,
                        "cabin": "ECONOMY",
                        "quotes": mock_raw_items,
                        "disclaimer": "SYNTHETIC DEMO / REPLAY DATA ONLY"
                    }
                    payload_hash = generate_payload_hash(raw_payload)

                    raw_resp = RawResponse(
                        collection_run_id=run.id,
                        source_name="DEMO_REPLAY_FEED",
                        collected_at=collection_date,
                        origin=origin,
                        destination=dest,
                        travel_date=travel_date,
                        advance_window_days=window,
                        payload_json=json.dumps(raw_payload),
                        payload_hash=payload_hash,
                        raw_content_type="application/json"
                    )
                    session.add(raw_resp)
                    session.flush()
                    total_responses += 1

                    # 3. Create FareQuote records from the raw response items
                    for item in mock_raw_items:
                        quote = FareQuote(
                            collection_run_id=run.id,
                            source_name="DEMO_REPLAY_FEED",
                            source_type="DEMO",
                            collected_at=collection_date,
                            origin=origin,
                            destination=dest,
                            travel_date=travel_date,
                            advance_window_days=window,
                            airline_code=item["airline_code"],
                            airline_name=item["airline_name"],
                            flight_number=item["flight_number"],
                            departure_time=datetime.datetime.fromisoformat(item["dep_time"]),
                            arrival_time=datetime.datetime.fromisoformat(item["arr_time"]),
                            stop_count=item["stop_count"],
                            fare_class=item["fare_class"],
                            base_fare=item["base_fare"],
                            taxes=item["taxes"],
                            mandatory_charges=item["mandatory_charges"],
                            total_fare=item["total_fare"],
                            currency=item["currency"],
                            availability_status="AVAILABLE",
                            raw_response_id=raw_resp.id,
                            duplicate_flag=False,
                            outlier_flag=False,
                            validation_notes="Synthetic seed data for local testing; conforms to fixed pilot rules"
                        )
                        session.add(quote)
                        run_quotes_count += 1
                        total_quotes += 1

            run.records_collected = run_quotes_count

        # 4. Create SourceHealth records
        health_now = datetime.datetime.now(datetime.timezone.utc)
        health = SourceHealth(
            source_name="DEMO_REPLAY_FEED",
            checked_at=health_now,
            status="HEALTHY",
            last_successful_collection=health_now,
            success_rate=100.0,
            missing_observations=0,
            http_error_count=0,
            parsing_error_count=0,
            captcha_count=0,
            average_response_time=1.12
        )
        session.add(health)

        session.commit()
        print(f"[SUCCESS] Seeded {days_back + 1} collection runs.")
        print(f"[SUCCESS] Seeded {total_responses} raw response snapshots.")
        print(f"[SUCCESS] Seeded {total_quotes} normalized pilot fare quotes.")
        print(f"[SUCCESS] Source health entry for 'DEMO_REPLAY_FEED' initialized.")

    except Exception as e:
        session.rollback()
        print(f"[ERROR] Failed to seed demo data: {e}")
        raise e
    finally:
        session.close()

if __name__ == "__main__":
    seed_demo_data(days_back=30)
