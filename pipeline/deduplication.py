import logging
from typing import Dict, Any, List
from collections import defaultdict
from sqlalchemy.orm import Session
from database.models import FareQuote

logger = logging.getLogger("apix.pipeline.deduplication")

def flag_duplicates(session: Session) -> Dict[str, Any]:
    """
    Identifies exact duplicates using:
    - source_name
    - origin
    - destination
    - travel_date
    - flight_number
    - total_fare
    - collection timestamp/run logic

    Marks subsequent matching quotes with duplicate_flag = True
    and records audit notes. Preserves historical data without silent drops.
    """
    quotes = (
        session.query(FareQuote)
        .order_by(
            FareQuote.origin,
            FareQuote.destination,
            FareQuote.travel_date,
            FareQuote.flight_number,
            FareQuote.collected_at.asc(),
            FareQuote.id.asc()
        )
        .all()
    )

    seen_groups = {}
    flagged_count = 0
    total_quotes = len(quotes)

    for q in quotes:
        # Composite signature for an exact flight quote observation
        sig = (
            q.source_name,
            q.origin.strip().upper(),
            q.destination.strip().upper(),
            str(q.travel_date),
            q.flight_number.strip().upper(),
            round(float(q.total_fare), 2)
        )

        if sig in seen_groups:
            # Duplicate found
            first_id = seen_groups[sig]
            if not q.duplicate_flag:
                q.duplicate_flag = True
                note = f"[DUPLICATE] Exact match of quote ID {first_id}"
                q.validation_notes = f"{q.validation_notes} | {note}" if q.validation_notes else note
                flagged_count += 1
        else:
            seen_groups[sig] = q.id
            if q.duplicate_flag:
                # If it was erroneously flagged previously but is first
                q.duplicate_flag = False

    session.commit()
    logger.info(f"Deduplication completed. Total quotes: {total_quotes}, Duplicates flagged: {flagged_count}")
    return {
        "total_records": total_quotes,
        "duplicates_flagged": flagged_count,
        "unique_records": total_quotes - flagged_count,
        "duplicate_rate_pct": round((flagged_count / total_quotes * 100), 2) if total_quotes > 0 else 0.0
    }

def get_duplicate_stats(session: Session) -> Dict[str, Any]:
    """Returns quick count of flagged duplicates versus unique records."""
    total = session.query(FareQuote).count()
    duplicates = session.query(FareQuote).filter(FareQuote.duplicate_flag == True).count()
    return {
        "total_quotes": total,
        "duplicate_quotes": duplicates,
        "clean_quotes": total - duplicates,
        "duplicate_percentage": round((duplicates / total * 100), 2) if total > 0 else 0.0
    }
