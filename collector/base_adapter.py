import json
import time
import hashlib
import logging
import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any

from sqlalchemy.orm import Session
from database.connection import get_session_maker
from database.models import CollectionRun, RawResponse, FareQuote, SourceHealth, utc_now

logger = logging.getLogger("apix.collector")

@dataclass
class RawFetchResult:
    """Represents raw data retrieved from a permitted source."""
    success: bool
    payload: Dict[str, Any]
    status_code: int
    duration_seconds: float
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    is_blocked: bool = False
    raw_content_type: str = "application/json"

@dataclass
class ParsedFlightQuote:
    """Represents a validated, normalized fare observation."""
    airline_code: str
    airline_name: str
    flight_number: str
    departure_time: datetime.datetime
    arrival_time: datetime.datetime
    stop_count: int
    fare_class: str
    base_fare: float
    taxes: float
    mandatory_charges: float
    total_fare: float
    currency: str = "INR"
    availability_status: str = "AVAILABLE"
    validation_notes: Optional[str] = None

class BaseFlightAdapter(ABC):
    """
    Abstract Base Class for flight search collection adapters.
    Enforces strict safety, compliance, no-bypass, and single-retry policies.
    """
    def __init__(
        self,
        source_name: str,
        source_type: str = "PERMITTED_SOURCE",
        is_permitted: bool = True,
        rate_limit_delay_seconds: float = 2.0
    ):
        self.source_name = source_name
        self.source_type = source_type
        self.is_permitted = is_permitted
        self.rate_limit_delay_seconds = rate_limit_delay_seconds

    def check_compliance(self) -> bool:
        """Verifies this adapter is designated as a permitted source."""
        if not self.is_permitted:
            logger.error(f"[COMPLIANCE ERROR] Collection from source '{self.source_name}' is not permitted.")
            return False
        return True

    def detect_blocking_or_captcha(self, status_code: int, content: str) -> Tuple[bool, Optional[str]]:
        """
        Compliance Circuit Breaker:
        Checks for HTTP 403, 429, CAPTCHA, or access denial.
        DO NOT attempt bypass. Immediately trigger circuit breaker.
        """
        if status_code == 403:
            return True, "HTTP_403_FORBIDDEN"
        if status_code == 429:
            return True, "HTTP_429_RATE_LIMIT"

        lower_content = (content or "").lower()
        blocking_indicators = [
            "captcha",
            "access denied",
            "bot detection",
            "cloudflare",
            "please verify you are human",
            "perimeterx",
            "datadome",
            "distil"
        ]
        for indicator in blocking_indicators:
            if indicator in lower_content:
                return True, f"CAPTCHA_OR_ACCESS_DENIED ({indicator})"

        return False, None

    @abstractmethod
    def fetch_raw(
        self,
        origin: str,
        destination: str,
        travel_date: datetime.date,
        advance_window_days: int
    ) -> RawFetchResult:
        """
        Fetches raw data from the permitted source or fixture.
        Must be implemented by concrete adapters.
        """
        pass

    @abstractmethod
    def parse_raw(
        self,
        payload: Dict[str, Any],
        origin: str,
        destination: str,
        travel_date: datetime.date,
        advance_window_days: int
    ) -> List[ParsedFlightQuote]:
        """
        Extracts normalized flight quotes from raw payload.
        Must be implemented by concrete adapters.
        """
        pass

    def _compute_hash(self, payload: Dict[str, Any]) -> str:
        """Generates SHA-256 hash of payload for deduplication and audit."""
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def collect(
        self,
        origin: str,
        destination: str,
        advance_window_days: int,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Orchestrates an end-to-end collection cycle:
        1. Checks compliance
        2. Applies conservative rate-limit delay
        3. Records CollectionRun
        4. Fetches raw data
        5. Stores RawResponse (SHA-256 hashed, zero tokens/cookies/screenshots)
        6. Parses and stores normalized FareQuotes
        7. Updates SourceHealth
        """
        if not self.check_compliance():
            raise PermissionError(f"Collection from source '{self.source_name}' is not permitted.")

        # Respect source-defined conservative delay
        time.sleep(self.rate_limit_delay_seconds)

        own_session = False
        if session is None:
            SessionLocal = get_session_maker()
            session = SessionLocal()
            own_session = True

        today = datetime.date.today()
        travel_date = today + datetime.timedelta(days=advance_window_days)
        start_time = utc_now()

        # 1. Start CollectionRun
        run = CollectionRun(
            source_name=self.source_name,
            scheduled_at=start_time,
            started_at=start_time,
            status="RUNNING",
            records_collected=0
        )
        session.add(run)
        session.flush()

        try:
            # 2. Fetch raw data
            fetch_result = self.fetch_raw(origin, destination, travel_date, advance_window_days)

            # Circuit breaker check: Blocked / CAPTCHA / 403 / 429
            if fetch_result.is_blocked:
                run.status = "BLOCKED"
                run.error_type = fetch_result.error_type or "BLOCKED_BY_SOURCE"
                run.error_message = (
                    f"Collection halted due to access restriction: {fetch_result.error_message}. "
                    "Safety policy: NO bypass or retry attempted."
                )
                run.completed_at = utc_now()
                run.duration_seconds = fetch_result.duration_seconds
                self._update_health(session, blocked=True, error_type=run.error_type, duration=fetch_result.duration_seconds)
                session.commit()
                return {
                    "run_id": run.id,
                    "status": "BLOCKED",
                    "records_collected": 0,
                    "error": run.error_message
                }

            if not fetch_result.success:
                run.status = "FAILED"
                run.error_type = fetch_result.error_type or "FETCH_ERROR"
                run.error_message = fetch_result.error_message
                run.completed_at = utc_now()
                run.duration_seconds = fetch_result.duration_seconds
                self._update_health(session, http_error=True, duration=fetch_result.duration_seconds)
                session.commit()
                return {
                    "run_id": run.id,
                    "status": "FAILED",
                    "records_collected": 0,
                    "error": run.error_message
                }

            # 3. Store RawResponse
            payload_hash = self._compute_hash(fetch_result.payload)
            raw_response = RawResponse(
                collection_run_id=run.id,
                source_name=self.source_name,
                collected_at=start_time,
                origin=origin,
                destination=destination,
                travel_date=travel_date,
                advance_window_days=advance_window_days,
                payload_json=json.dumps(fetch_result.payload),
                payload_hash=payload_hash,
                raw_content_type=fetch_result.raw_content_type
            )
            session.add(raw_response)
            session.flush()

            # 4. Parse quotes
            parsed_quotes = self.parse_raw(
                fetch_result.payload,
                origin=origin,
                destination=destination,
                travel_date=travel_date,
                advance_window_days=advance_window_days
            )

            # 5. Store FareQuotes
            saved_count = 0
            for quote_data in parsed_quotes:
                fare_quote = FareQuote(
                    collection_run_id=run.id,
                    source_name=self.source_name,
                    source_type=self.source_type,
                    collected_at=start_time,
                    origin=origin,
                    destination=destination,
                    travel_date=travel_date,
                    advance_window_days=advance_window_days,
                    airline_code=quote_data.airline_code,
                    airline_name=quote_data.airline_name,
                    flight_number=quote_data.flight_number,
                    departure_time=quote_data.departure_time,
                    arrival_time=quote_data.arrival_time,
                    stop_count=quote_data.stop_count,
                    fare_class=quote_data.fare_class,
                    base_fare=quote_data.base_fare,
                    taxes=quote_data.taxes,
                    mandatory_charges=quote_data.mandatory_charges,
                    total_fare=quote_data.total_fare,
                    currency=quote_data.currency,
                    availability_status=quote_data.availability_status,
                    raw_response_id=raw_response.id,
                    duplicate_flag=False,
                    outlier_flag=False,
                    validation_notes=quote_data.validation_notes
                )
                session.add(fare_quote)
                saved_count += 1

            run.status = "SUCCESS"
            run.records_collected = saved_count
            run.completed_at = utc_now()
            run.duration_seconds = fetch_result.duration_seconds

            # 6. Update SourceHealth as healthy
            self._update_health(session, success=True, duration=fetch_result.duration_seconds)
            session.commit()

            return {
                "run_id": run.id,
                "status": "SUCCESS",
                "raw_response_id": raw_response.id,
                "records_collected": saved_count,
                "payload_hash": payload_hash
            }

        except Exception as e:
            session.rollback()
            logger.exception(f"Unexpected error in collector '{self.source_name}': {e}")
            run.status = "FAILED"
            run.error_type = type(e).__name__
            run.error_message = str(e)
            run.completed_at = utc_now()
            self._update_health(session, parsing_error=True)
            try:
                session.commit()
            except Exception:
                session.rollback()
            raise e
        finally:
            if own_session:
                session.close()

    def _update_health(
        self,
        session: Session,
        success: bool = False,
        blocked: bool = False,
        http_error: bool = False,
        parsing_error: bool = False,
        error_type: Optional[str] = None,
        duration: float = 0.0
    ):
        """Updates health statistics for the source."""
        health = session.query(SourceHealth).filter_by(source_name=self.source_name).first()
        if not health:
            health = SourceHealth(
                source_name=self.source_name,
                checked_at=utc_now(),
                status="HEALTHY",
                success_rate=100.0,
                missing_observations=0,
                http_error_count=0,
                parsing_error_count=0,
                captcha_count=0,
                average_response_time=duration
            )
            session.add(health)

        health.checked_at = utc_now()
        if duration > 0:
            health.average_response_time = round((health.average_response_time + duration) / 2, 2)

        if success:
            health.status = "HEALTHY"
            health.last_successful_collection = utc_now()
        elif blocked:
            health.status = "BLOCKED"
            health.captcha_count += 1
            health.success_rate = max(0.0, health.success_rate - 10.0)
        elif http_error:
            health.status = "DEGRADED"
            health.http_error_count += 1
            health.success_rate = max(0.0, health.success_rate - 5.0)
        elif parsing_error:
            health.status = "DEGRADED"
            health.parsing_error_count += 1
            health.success_rate = max(0.0, health.success_rate - 5.0)
