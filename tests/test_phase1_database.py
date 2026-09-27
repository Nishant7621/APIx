import pytest
import datetime
from sqlalchemy import inspect
from database.connection import get_engine, get_session_maker, Base
from database.models import CollectionRun, RawResponse, FareQuote, SourceHealth
from database.seed_demo_data import generate_payload_hash

def get_utc():
    return datetime.datetime.now(datetime.timezone.utc)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="session")
def engine():
    eng = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=eng)
    yield eng

@pytest.fixture(scope="function")
def db_session(engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()

def test_database_tables_exist(engine):
    """Verify all 4 required tables are created in the database schema."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "collection_runs" in tables
    assert "raw_responses" in tables
    assert "fare_quotes" in tables
    assert "source_health" in tables

def test_collection_run_lifecycle(db_session):
    """Verify CollectionRun can be created, updated, and queried."""
    run = CollectionRun(
        source_name="TEST_SOURCE",
        scheduled_at=get_utc(),
        started_at=get_utc(),
        status="RUNNING",
        records_collected=0
    )
    db_session.add(run)
    db_session.commit()

    assert run.id is not None
    assert run.status == "RUNNING"

    # Complete the run
    run.status = "SUCCESS"
    run.records_collected = 10
    run.completed_at = get_utc()
    run.duration_seconds = 4.5
    db_session.commit()

    fetched = db_session.query(CollectionRun).filter_by(id=run.id).first()
    assert fetched.status == "SUCCESS"
    assert fetched.records_collected == 10
    assert fetched.duration_seconds == 4.5

def test_raw_response_and_payload_hash(db_session):
    """Verify RawResponse correctly stores payload and SHA-256 hash."""
    run = CollectionRun(source_name="TEST_HASH", status="SUCCESS")
    db_session.add(run)
    db_session.flush()

    payload = {"origin": "DEL", "destination": "BOM", "price": 4500}
    p_hash = generate_payload_hash(payload)

    raw = RawResponse(
        collection_run_id=run.id,
        source_name="TEST_HASH",
        collected_at=get_utc(),
        origin="DEL",
        destination="BOM",
        travel_date=datetime.date.today() + datetime.timedelta(days=7),
        advance_window_days=7,
        payload_json='{"origin": "DEL", "destination": "BOM", "price": 4500}',
        payload_hash=p_hash,
        raw_content_type="application/json"
    )
    db_session.add(raw)
    db_session.commit()

    assert raw.id is not None
    assert len(raw.payload_hash) == 64  # SHA-256 hex length
    assert raw.advance_window_days == 7

def test_fare_quote_pilot_rules(db_session):
    """Verify FareQuote satisfies fixed pilot rules (INR, positive values, component sum)."""
    run = CollectionRun(source_name="TEST_QUOTE", status="SUCCESS")
    db_session.add(run)
    db_session.flush()

    base = 3500.0
    tax = 800.0
    charges = 200.0
    total = base + tax + charges

    quote = FareQuote(
        collection_run_id=run.id,
        source_name="TEST_QUOTE",
        source_type="DEMO",
        collected_at=get_utc(),
        origin="DEL",
        destination="BOM",
        travel_date=datetime.date.today() + datetime.timedelta(days=1),
        advance_window_days=1,
        airline_code="6E",
        airline_name="IndiGo",
        flight_number="6E-204",
        departure_time=get_utc(),
        arrival_time=get_utc() + datetime.timedelta(hours=2),
        stop_count=0,
        fare_class="ECONOMY",
        base_fare=base,
        taxes=tax,
        mandatory_charges=charges,
        total_fare=total,
        currency="INR",
        availability_status="AVAILABLE",
        duplicate_flag=False,
        outlier_flag=False,
        validation_notes="Demo test quote"
    )
    db_session.add(quote)
    db_session.commit()

    fetched = db_session.query(FareQuote).filter_by(id=quote.id).first()
    assert fetched.currency == "INR"
    assert fetched.total_fare > 0
    assert round(fetched.base_fare + fetched.taxes + fetched.mandatory_charges, 2) == round(fetched.total_fare, 2)
    assert fetched.stop_count == 0  # direct flight

def test_source_health_tracking(db_session):
    """Verify SourceHealth monitors latency, errors, and captcha counts."""
    health = SourceHealth(
        source_name="TEST_HEALTH_SOURCE",
        checked_at=get_utc(),
        status="HEALTHY",
        success_rate=98.5,
        missing_observations=2,
        http_error_count=1,
        parsing_error_count=0,
        captcha_count=0,
        average_response_time=1.45
    )
    db_session.add(health)
    db_session.commit()

    fetched = db_session.query(SourceHealth).filter_by(source_name="TEST_HEALTH_SOURCE").first()
    assert fetched.status == "HEALTHY"
    assert fetched.captcha_count == 0
    assert fetched.success_rate == 98.5

