import json
import time
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from collector.base_adapter import (
    BaseFlightAdapter,
    RawFetchResult,
    ParsedFlightQuote
)

# =============================================================================
# EXTENSION POINT GUIDE: WHERE TO INSERT AN APPROVED SOURCE URL & RULES
# =============================================================================
# When you have obtained permission or an authorized API key for a public source:
# 1. Update APPROVED_ENDPOINT below with your permitted URL.
# 2. In fetch_raw(), switch from fixture loading to httpx.get() or Playwright.
# 3. In parse_raw(), update field mappings to match the approved source's JSON/HTML schema.
# 4. Respect robots.txt, rate limits (rate_limit_delay_seconds), and never bypass CAPTCHA.
# =============================================================================
APPROVED_ENDPOINT: Optional[str] = None  # e.g., "https://api.approved-source.example/v1/flights"

class ExamplePermittedAdapter(BaseFlightAdapter):
    """
    Placeholder/Example adapter demonstrating permitted collection.
    By default, uses safe local mock fixtures to avoid hitting restricted websites.
    """
    def __init__(
        self,
        fixture_path: Optional[Path] = None,
        simulate_circuit_breaker: Optional[str] = None
    ):
        super().__init__(
            source_name="PERMITTED_EXAMPLE_FEED",
            source_type="AIRLINE_PORTAL",
            is_permitted=True,
            rate_limit_delay_seconds=0.1  # Fast for testing; set to 2.0+ for live permitted sources
        )
        self.fixture_path = fixture_path or (
            Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "mock_del_bom_t7_response.json"
        )
        self.simulate_circuit_breaker = simulate_circuit_breaker

    def fetch_raw(
        self,
        origin: str,
        destination: str,
        travel_date: datetime.date,
        advance_window_days: int
    ) -> RawFetchResult:
        """
        Fetches flight search payload.
        Adheres to DEL-BOM at T+7 for initial validation.
        """
        start_time = time.time()

        # Simulate Circuit Breakers for safety testing (e.g. 403, 429, CAPTCHA)
        if self.simulate_circuit_breaker == "CAPTCHA":
            return RawFetchResult(
                success=False,
                payload={},
                status_code=200,
                duration_seconds=round(time.time() - start_time, 3),
                error_type="CAPTCHA_DETECTED",
                error_message="Access denied: CAPTCHA prompt detected on response page",
                is_blocked=True
            )
        elif self.simulate_circuit_breaker == "403":
            return RawFetchResult(
                success=False,
                payload={},
                status_code=403,
                duration_seconds=round(time.time() - start_time, 3),
                error_type="HTTP_403_FORBIDDEN",
                error_message="HTTP 403 Forbidden - Access control refused request",
                is_blocked=True
            )

        # ---------------------------------------------------------------------
        # [EXTENSION POINT]: LIVE HTTPX / PLAYWRIGHT FETCH FOR APPROVED SOURCE
        # ---------------------------------------------------------------------
        # If APPROVED_ENDPOINT is configured and source terms permit:
        #
        # import httpx
        # response = httpx.get(
        #     APPROVED_ENDPOINT,
        #     params={"from": origin, "to": destination, "date": str(travel_date)},
        #     headers={"User-Agent": "APIx Research Bot/1.0"},
        #     timeout=30.0
        # )
        # is_blocked, block_reason = self.detect_blocking_or_captcha(response.status_code, response.text)
        # if is_blocked:
        #     return RawFetchResult(..., is_blocked=True, error_type=block_reason)
        # payload = response.json()
        # ---------------------------------------------------------------------

        # Default Safe Mode: Load from permitted mock fixture
        if not self.fixture_path.exists():
            return RawFetchResult(
                success=False,
                payload={},
                status_code=404,
                duration_seconds=round(time.time() - start_time, 3),
                error_type="FIXTURE_NOT_FOUND",
                error_message=f"Fixture file not found at {self.fixture_path}",
                is_blocked=False
            )

        with open(self.fixture_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        # Override search_params with the requested parameters
        payload["search_params"] = {
            "origin": origin,
            "destination": destination,
            "cabin_class": "ECONOMY",
            "passenger_count": 1,
            "currency": "INR",
            "advance_window_days": advance_window_days,
            "travel_date": str(travel_date)
        }

        duration = round(time.time() - start_time, 3)
        return RawFetchResult(
            success=True,
            payload=payload,
            status_code=200,
            duration_seconds=duration,
            is_blocked=False,
            raw_content_type="application/json"
        )

    def parse_raw(
        self,
        payload: Dict[str, Any],
        origin: str,
        destination: str,
        travel_date: datetime.date,
        advance_window_days: int
    ) -> List[ParsedFlightQuote]:
        """
        Parses raw JSON payload into normalized flight quotes.
        Ensures direct vs connecting distinction and mandatory payable fare consistency.
        """
        # ---------------------------------------------------------------------
        # [EXTENSION POINT]: FIELD EXTRACTION RULES FOR APPROVED SOURCE
        # ---------------------------------------------------------------------
        # Adjust the dictionary keys below to match your approved source schema:
        # ---------------------------------------------------------------------
        flights_data = payload.get("flights", [])
        parsed_quotes: List[ParsedFlightQuote] = []

        for item in flights_data:
            fare_details = item.get("fare_details", {})
            base_fare = float(fare_details.get("base_fare", 0.0))
            taxes = float(fare_details.get("taxes", 0.0))
            mandatory_charges = float(fare_details.get("mandatory_charges", 0.0))
            total_fare = float(fare_details.get("total_fare", base_fare + taxes + mandatory_charges))

            dep_dt = datetime.datetime.fromisoformat(item["departure_time"])
            arr_dt = datetime.datetime.fromisoformat(item["arrival_time"])

            quote = ParsedFlightQuote(
                airline_code=item.get("airline_code", "XX"),
                airline_name=item.get("airline_name", "Unknown Airline"),
                flight_number=item.get("flight_number", "FL-000"),
                departure_time=dep_dt,
                arrival_time=arr_dt,
                stop_count=int(item.get("stop_count", 0)),
                fare_class=item.get("fare_class", "ECONOMY"),
                base_fare=base_fare,
                taxes=taxes,
                mandatory_charges=mandatory_charges,
                total_fare=total_fare,
                currency=fare_details.get("currency", "INR"),
                availability_status=item.get("availability", "AVAILABLE"),
                validation_notes="Collected via ExamplePermittedAdapter"
            )
            parsed_quotes.append(quote)

        return parsed_quotes
