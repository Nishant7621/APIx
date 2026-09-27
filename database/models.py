import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Date,
    Text,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship
from database.connection import Base

def utc_now():
    """Returns current UTC timestamp (timezone-aware)."""
    return datetime.datetime.now(datetime.timezone.utc)

class CollectionRun(Base):
    """
    Represents an execution cycle of data collection for an approved source.
    """
    __tablename__ = "collection_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String(100), nullable=False, index=True)
    scheduled_at = Column(DateTime, nullable=False, default=utc_now)
    started_at = Column(DateTime, nullable=False, default=utc_now)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False, default="RUNNING")  # PENDING, RUNNING, SUCCESS, PARTIAL, FAILED, BLOCKED
    records_collected = Column(Integer, nullable=False, default=0)
    error_type = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Relationships
    raw_responses = relationship("RawResponse", back_populates="collection_run", cascade="all, delete-orphan")
    fare_quotes = relationship("FareQuote", back_populates="collection_run", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CollectionRun id={self.id} source='{self.source_name}' status='{self.status}' records={self.records_collected}>"


class RawResponse(Base):
    """
    Stores unmodified permitted raw responses or relevant HTML/JSON fragments.
    Strictly forbids storing full page assets, screenshots, cookies, or tokens.
    """
    __tablename__ = "raw_responses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_run_id = Column(Integer, ForeignKey("collection_runs.id"), nullable=False, index=True)
    source_name = Column(String(100), nullable=False, index=True)
    collected_at = Column(DateTime, nullable=False, default=utc_now)
    origin = Column(String(3), nullable=False, index=True)
    destination = Column(String(3), nullable=False, index=True)
    travel_date = Column(Date, nullable=False, index=True)
    advance_window_days = Column(Integer, nullable=False, index=True)
    payload_json = Column(Text, nullable=False)
    payload_hash = Column(String(64), nullable=False, index=True)  # SHA-256 for duplicate and integrity checks
    raw_content_type = Column(String(50), nullable=False, default="application/json")

    # Relationships
    collection_run = relationship("CollectionRun", back_populates="raw_responses")
    fare_quotes = relationship("FareQuote", back_populates="raw_response")

    def __repr__(self):
        return f"<RawResponse id={self.id} {self.origin}->{self.destination} date={self.travel_date} window=T+{self.advance_window_days}>"


class FareQuote(Base):
    """
    Normalized, cleaned, and validated fare quotes extracted from raw responses.
    Adheres strictly to pilot rules (Economy, 1 adult, INR, direct vs connecting).
    """
    __tablename__ = "fare_quotes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_run_id = Column(Integer, ForeignKey("collection_runs.id"), nullable=False, index=True)
    source_name = Column(String(100), nullable=False, index=True)
    source_type = Column(String(50), nullable=False, default="DEMO")  # AIRLINE, OTA, METASEARCH, DEMO
    collected_at = Column(DateTime, nullable=False, default=utc_now, index=True)
    origin = Column(String(3), nullable=False, index=True)
    destination = Column(String(3), nullable=False, index=True)
    travel_date = Column(Date, nullable=False, index=True)
    advance_window_days = Column(Integer, nullable=False, index=True)
    airline_code = Column(String(10), nullable=True, index=True)
    airline_name = Column(String(100), nullable=True)
    flight_number = Column(String(20), nullable=True)
    departure_time = Column(DateTime, nullable=True)
    arrival_time = Column(DateTime, nullable=True)
    stop_count = Column(Integer, nullable=False, default=0)  # 0: Direct, 1+: Connecting
    fare_class = Column(String(50), nullable=False, default="ECONOMY")
    base_fare = Column(Float, nullable=True)
    taxes = Column(Float, nullable=True)
    mandatory_charges = Column(Float, nullable=True, default=0.0)
    total_fare = Column(Float, nullable=True, index=True)
    currency = Column(String(3), nullable=False, default="INR")
    availability_status = Column(String(50), nullable=False, default="AVAILABLE")
    raw_response_id = Column(Integer, ForeignKey("raw_responses.id"), nullable=True, index=True)
    duplicate_flag = Column(Boolean, nullable=False, default=False)
    outlier_flag = Column(Boolean, nullable=False, default=False)
    validation_notes = Column(Text, nullable=True)

    # Relationships
    collection_run = relationship("CollectionRun", back_populates="fare_quotes")
    raw_response = relationship("RawResponse", back_populates="fare_quotes")

    __table_args__ = (
        Index("ix_fare_quotes_route_window_date", "origin", "destination", "advance_window_days", "travel_date"),
    )

    def __repr__(self):
        return f"<FareQuote id={self.id} {self.flight_number} {self.origin}->{self.destination} total={self.total_fare} {self.currency}>"


class SourceHealth(Base):
    """
    Monitors reliability, latency, and blocking indicators for each approved collection source.
    """
    __tablename__ = "source_health"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String(100), nullable=False, index=True)
    checked_at = Column(DateTime, nullable=False, default=utc_now)
    status = Column(String(50), nullable=False, default="HEALTHY")  # HEALTHY, DEGRADED, BLOCKED, CAPTCHA_TRIGGERED, DOWN
    last_successful_collection = Column(DateTime, nullable=True)
    success_rate = Column(Float, nullable=False, default=100.0)  # Percentage 0.0 - 100.0
    missing_observations = Column(Integer, nullable=False, default=0)
    http_error_count = Column(Integer, nullable=False, default=0)
    parsing_error_count = Column(Integer, nullable=False, default=0)
    captcha_count = Column(Integer, nullable=False, default=0)
    average_response_time = Column(Float, nullable=False, default=0.0)  # Seconds

    def __repr__(self):
        return f"<SourceHealth source='{self.source_name}' status='{self.status}' success_rate={self.success_rate}%>"
