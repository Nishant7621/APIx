from typing import Optional, List
from pydantic import BaseModel, Field

class QuoteResponse(BaseModel):
    id: int
    source_name: str
    source_type: str
    route: str
    origin: str
    destination: str
    advance_window_days: int
    airline_code: Optional[str] = None
    airline_name: Optional[str] = None
    flight_number: Optional[str] = None
    stop_count: int
    fare_class: str
    base_fare: Optional[float] = None
    taxes: Optional[float] = None
    mandatory_charges: Optional[float] = None
    total_fare: float
    currency: str
    travel_date: str
    collected_at: str
    duplicate_flag: bool
    outlier_flag: bool

class APIxTrendItem(BaseModel):
    collection_date: str
    advance_window_days: int
    apix_index: Optional[float] = None
    rolling_volatility: Optional[float] = None
    is_complete: bool

class DailyMedianItem(BaseModel):
    collection_date: str
    route: str
    advance_window_days: int
    daily_median_price: float
    quote_count: int

class CollectionRunResponse(BaseModel):
    id: int
    source_name: str
    status: str
    records_collected: int
    duration_seconds: Optional[float] = None
    started_at: str
    completed_at: Optional[str] = None
    error_type: Optional[str] = None

class SourceHealthResponse(BaseModel):
    source_name: str
    status: str
    success_rate: float
    captcha_count: int
    http_error_count: int
    parsing_error_count: int
    average_response_time: float
    last_successful_collection: Optional[str] = None

class SystemSummaryResponse(BaseModel):
    system_status: str
    total_collection_runs: int
    total_quotes: int
    clean_quotes: int
    flagged_duplicates: int
    flagged_outliers: int
    current_apix_t7: Optional[float] = None
    latest_collection_timestamp: Optional[str] = None

class OTAPlatformItem(BaseModel):
    platform_name: str
    source_type: str
    sampled_quotes: int
    average_fare: float
    average_convenience_fee: float
    spread_vs_market_avg_pct: float

class OTABenchmarkResponse(BaseModel):
    market_average_fare: float
    cheapest_platform: str
    costliest_platform: str
    platforms: List[OTAPlatformItem]

class TimelineDataPoint(BaseModel):
    label: str
    sub_label: Optional[str] = None
    average_all_otas: float
    makemytrip: float
    easemytrip: float
    yatra: float
    cleartrip: float
    ixigo: float
    direct_portal: float
    indigo: float
    air_india: float
    akasa_air: float
    spicejet: float
    apix_composite: float
    booking_velocity: float
    price_velocity: float
    is_peak: bool

class TimelineResponse(BaseModel):
    timeframe: str
    granularity: str
    total_data_points: int
    peak_booking_period: str
    peak_price_surge_pct: float
    points: List[TimelineDataPoint]

class CollectionHealthItem(BaseModel):
    source_name: str
    expected_searches: int
    successful_searches: int
    missing_count: int
    captcha_count: int
    http_error_count: int
    parsing_error_count: int
    last_successful_run: Optional[str] = None
    status: str
    success_rate_pct: float

class CollectionHealthSummaryResponse(BaseModel):
    selected_start_date: str
    selected_end_date: str
    total_sources_monitored: int
    total_expected: int
    total_successful: int
    total_missing: int
    no_restrictions_observed: bool
    restriction_message: str
    sources: List[CollectionHealthItem]


