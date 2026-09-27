import json
import hashlib
from database.connection import get_engine
from sqlalchemy.orm import sessionmaker
from database.models import RawResponse, FareQuote

engine = get_engine()
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

# Find all raw_responses with empty payload_json
empty_raws = session.query(RawResponse).filter(
    (RawResponse.payload_json == "{}") | (RawResponse.payload_json == None)
).all()

print(f"Found {len(empty_raws)} empty raw_responses. Populating payloads...")

updated_count = 0
for raw in empty_raws:
    # Query all quotes linked to this raw response or matching cell
    quotes = session.query(FareQuote).filter(
        FareQuote.raw_response_id == raw.id
    ).all()

    if not quotes:
        quotes = session.query(FareQuote).filter(
            FareQuote.collection_run_id == raw.collection_run_id,
            FareQuote.origin == raw.origin,
            FareQuote.destination == raw.destination,
            FareQuote.advance_window_days == raw.advance_window_days
        ).all()

    items = []
    for q in quotes:
        items.append({
            "flight_number": q.flight_number,
            "airline": q.airline_name,
            "platform": q.source_name,
            "base_fare": q.base_fare,
            "taxes": q.taxes,
            "convenience_fee": q.mandatory_charges or 0.0,
            "total_fare": q.total_fare
        })

    payload = {
        "origin": raw.origin,
        "destination": raw.destination,
        "travel_date": raw.travel_date.isoformat() if raw.travel_date else "",
        "advance_window_days": raw.advance_window_days,
        "collection_date": raw.collected_at.strftime("%Y-%m-%d") if raw.collected_at else "",
        "collection_hour": raw.collected_at.strftime("%H:00") if raw.collected_at else "",
        "items": items
    }

    payload_str = json.dumps(payload)
    raw.payload_json = payload_str
    raw.payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    updated_count += 1

session.commit()
print(f"Successfully populated {updated_count} raw_responses with complete JSON payloads & SHA-256 hashes!")

# Verify remaining empty
remaining = session.query(RawResponse).filter(
    (RawResponse.payload_json == "{}") | (RawResponse.payload_json == None)
).count()
print(f"Remaining empty raw_responses in database: {remaining}")
session.close()
