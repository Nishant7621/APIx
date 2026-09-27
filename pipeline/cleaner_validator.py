import logging
import re
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from database.models import FareQuote

logger = logging.getLogger("apix.pipeline.cleaner")

# Known IATA airport codes for standard Indian routes
STANDARD_AIRPORTS = {"DEL", "BOM", "BLR", "CCU", "HYD", "MAA", "GOI", "PNQ", "AMD", "COK"}

# Standard Indian airline codes
STANDARD_AIRLINES = {
    "6E": "IndiGo",
    "AI": "Air India",
    "QP": "Akasa Air",
    "SG": "SpiceJet",
    "UK": "Vistara",
    "IX": "Air India Express",
    "I5": "AIX Connect"
}

def standardize_and_validate(session: Session) -> Dict[str, Any]:
    """
    Standardizes codes and validates fare consistency across all quotes:
    - Standardizes origin/destination to uppercase 3-letter IATA codes.
    - Standardizes airline codes and airline names.
    - Standardizes currency to uppercase 'INR'.
    - Validates total fare > 0 and components (base + tax + charges == total).
    - Flags missing or inconsistent fields into validation_notes without dropping data.
    """
    quotes = session.query(FareQuote).all()
    total_quotes = len(quotes)
    standardized_count = 0
    invalidation_count = 0

    for q in quotes:
        issues: List[str] = []

        # 1. Standardize Airport Codes
        clean_orig = (q.origin or "").strip().upper()
        clean_dest = (q.destination or "").strip().upper()

        if len(clean_orig) != 3:
            issues.append(f"Invalid origin code '{q.origin}'")
        elif clean_orig != q.origin:
            q.origin = clean_orig
            standardized_count += 1

        if len(clean_dest) != 3:
            issues.append(f"Invalid destination code '{q.destination}'")
        elif clean_dest != q.destination:
            q.destination = clean_dest
            standardized_count += 1

        # 2. Standardize Airline Code & Name
        clean_airline = (q.airline_code or "").strip().upper()
        if clean_airline != q.airline_code:
            q.airline_code = clean_airline
            standardized_count += 1

        if clean_airline in STANDARD_AIRLINES and not q.airline_name:
            q.airline_name = STANDARD_AIRLINES[clean_airline]

        # 3. Standardize Currency
        clean_currency = (q.currency or "").strip().upper()
        if clean_currency != "INR":
            issues.append(f"Non-INR currency '{q.currency}'")
        elif clean_currency != q.currency:
            q.currency = clean_currency
            standardized_count += 1

        # 4. Standardize Flight Number
        clean_flight_num = (q.flight_number or "").strip().upper()
        if not clean_flight_num:
            issues.append("Missing flight_number")
        elif clean_flight_num != q.flight_number:
            q.flight_number = clean_flight_num

        # 5. Check Timestamps
        if not q.departure_time:
            issues.append("Missing departure_time")
        if not q.arrival_time:
            issues.append("Missing arrival_time")
        elif q.departure_time and q.arrival_time and q.arrival_time <= q.departure_time:
            issues.append("arrival_time before or equal to departure_time")

        # 6. Validate Fare Values (Strict Pilot Rule: non-negative & component consistency)
        if q.total_fare is None or q.total_fare <= 0:
            issues.append(f"Invalid total_fare ({q.total_fare}); must be strictly positive")

        if (q.base_fare is not None and q.base_fare < 0) or \
           (q.taxes is not None and q.taxes < 0) or \
           (q.mandatory_charges is not None and q.mandatory_charges < 0):
            issues.append("Negative component fare detected")

        if q.base_fare is not None and q.taxes is not None and q.mandatory_charges is not None and q.total_fare is not None:
            comp_sum = round(q.base_fare + q.taxes + q.mandatory_charges, 2)
            tot = round(q.total_fare, 2)
            if abs(comp_sum - tot) > 1.0:  # Allow max 1 rupee rounding divergence
                issues.append(f"Component mismatch: Base({q.base_fare}) + Tax({q.taxes}) + Charges({q.mandatory_charges}) = {comp_sum} != Total({tot})")

        # 7. Record Issues in validation_notes
        if issues:
            invalidation_count += 1
            existing = q.validation_notes or ""
            new_notes = "; ".join(issues)
            if new_notes not in existing:
                q.validation_notes = f"{existing} | [VALIDATION_FAIL: {new_notes}]" if existing else f"[VALIDATION_FAIL: {new_notes}]"

    session.commit()
    logger.info(f"Validation completed. Total: {total_quotes}, Standardized: {standardized_count}, Issues flagged: {invalidation_count}")
    return {
        "total_records": total_quotes,
        "standardized_fields_count": standardized_count,
        "records_with_validation_issues": invalidation_count,
        "clean_record_percentage": round(((total_quotes - invalidation_count) / total_quotes * 100), 2) if total_quotes > 0 else 0.0
    }
