import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.models import CollectionRun, FareQuote, utc_now
from pipeline.deduplication import flag_duplicates, get_duplicate_stats
from pipeline.cleaner_validator import standardize_and_validate
from pipeline.outliers import detect_outliers_iqr_mad
from pipeline.missing_data_report import generate_missing_data_report

@pytest.fixture
def test_session():
    """Provides an isolated in-memory SQLite database session for Phase 3 tests."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create dummy collection run
    run = CollectionRun(source_name="TEST_PIPELINE", status="SUCCESS")
    session.add(run)
    session.commit()

    yield session
    session.close()

def test_deduplication_exact_matches(test_session):
    """Verify duplicate observations are flagged without dropping data."""
    run = test_session.query(CollectionRun).first()
    t_date = datetime.date(2026, 10, 1)

    # Insert two identical quotes
    q1 = FareQuote(
        collection_run_id=run.id,
        source_name="TEST_FEED",
        source_type="OTA",
        origin="DEL",
        destination="BOM",
        travel_date=t_date,
        advance_window_days=7,
        airline_code="6E",
        airline_name="IndiGo",
        flight_number="6E-101",
        departure_time=utc_now(),
        arrival_time=utc_now() + datetime.timedelta(hours=2),
        stop_count=0,
        fare_class="ECONOMY",
        base_fare=3500.0,
        taxes=1000.0,
        mandatory_charges=200.0,
        total_fare=4700.0,
        currency="INR",
        duplicate_flag=False
    )
    q2 = FareQuote(
        collection_run_id=run.id,
        source_name="TEST_FEED",
        source_type="OTA",
        origin="DEL",
        destination="BOM",
        travel_date=t_date,
        advance_window_days=7,
        airline_code="6E",
        airline_name="IndiGo",
        flight_number="6E-101",
        departure_time=utc_now(),
        arrival_time=utc_now() + datetime.timedelta(hours=2),
        stop_count=0,
        fare_class="ECONOMY",
        base_fare=3500.0,
        taxes=1000.0,
        mandatory_charges=200.0,
        total_fare=4700.0,
        currency="INR",
        duplicate_flag=False
    )
    test_session.add_all([q1, q2])
    test_session.commit()

    res = flag_duplicates(test_session)
    assert res["total_records"] == 2
    assert res["duplicates_flagged"] == 1

    refreshed_q1 = test_session.query(FareQuote).filter_by(id=q1.id).first()
    refreshed_q2 = test_session.query(FareQuote).filter_by(id=q2.id).first()
    assert refreshed_q1.duplicate_flag is False
    assert refreshed_q2.duplicate_flag is True
    assert "[DUPLICATE]" in refreshed_q2.validation_notes

def test_standardization_and_validation(test_session):
    """Verify code uppercase standardization and invalid fare flagging."""
    run = test_session.query(CollectionRun).first()
    t_date = datetime.date(2026, 10, 1)

    # Quote with lowercase codes and component mismatch
    quote = FareQuote(
        collection_run_id=run.id,
        source_name="TEST_FEED",
        source_type="OTA",
        origin="del",          # lowercase
        destination="bom",     # lowercase
        travel_date=t_date,
        advance_window_days=7,
        airline_code="6e",     # lowercase
        flight_number="6e-202",
        departure_time=utc_now(),
        arrival_time=utc_now() + datetime.timedelta(hours=2),
        stop_count=0,
        fare_class="ECONOMY",
        base_fare=3000.0,
        taxes=500.0,
        mandatory_charges=100.0,
        total_fare=9999.0,      # Major mismatch with components
        currency="inr",        # lowercase
        duplicate_flag=False
    )
    test_session.add(quote)
    test_session.commit()

    val_res = standardize_and_validate(test_session)
    assert val_res["records_with_validation_issues"] >= 1

    refreshed = test_session.query(FareQuote).filter_by(id=quote.id).first()
    assert refreshed.origin == "DEL"
    assert refreshed.destination == "BOM"
    assert refreshed.airline_code == "6E"
    assert refreshed.currency == "INR"
    assert "Component mismatch" in refreshed.validation_notes

def test_outlier_detection_iqr_mad(test_session):
    """Verify transparent IQR/MAD outlier flagging without dropping data."""
    run = test_session.query(CollectionRun).first()
    t_date = datetime.date(2026, 10, 5)

    # Cluster of normal prices around 4,500 - 5,200 INR
    quotes = []
    normal_prices = [4500.0, 4600.0, 4700.0, 4800.0, 4900.0, 5000.0, 5100.0, 5200.0]
    for i, p in enumerate(normal_prices):
        q = FareQuote(
            collection_run_id=run.id,
            source_name="TEST_FEED",
            source_type="OTA",
            origin="DEL",
            destination="BOM",
            travel_date=t_date,
            advance_window_days=15,
            airline_code="6E",
            airline_name="IndiGo",
            flight_number=f"6E-{300+i}",
            departure_time=utc_now(),
            arrival_time=utc_now() + datetime.timedelta(hours=2),
            stop_count=0,
            base_fare=p * 0.7,
            taxes=p * 0.2,
            mandatory_charges=p * 0.1,
            total_fare=p,
            currency="INR",
            duplicate_flag=False
        )
        quotes.append(q)

    # Extreme Outlier (e.g. 35,000 INR)
    outlier_quote = FareQuote(
        collection_run_id=run.id,
        source_name="TEST_FEED",
        source_type="OTA",
        origin="DEL",
        destination="BOM",
        travel_date=t_date,
        advance_window_days=15,
        airline_code="AI",
        airline_name="Air India",
        flight_number="AI-9999",
        departure_time=utc_now(),
        arrival_time=utc_now() + datetime.timedelta(hours=2),
        stop_count=0,
        base_fare=25000.0,
        taxes=8000.0,
        mandatory_charges=2000.0,
        total_fare=35000.0,
        currency="INR",
        duplicate_flag=False
    )
    quotes.append(outlier_quote)

    test_session.add_all(quotes)
    test_session.commit()

    res = detect_outliers_iqr_mad(test_session, iqr_multiplier=1.5, mad_threshold=3.0)
    assert res["total_flagged_outliers"] >= 1

    # Check that outlier is flagged and NOT deleted
    refreshed_outlier = test_session.query(FareQuote).filter_by(id=outlier_quote.id).first()
    assert refreshed_outlier is not None
    assert refreshed_outlier.outlier_flag is True
    assert "[OUTLIER" in refreshed_outlier.validation_notes

def test_missing_data_report_generation(test_session):
    """Verify missing data report produces correct structure and coverage metrics."""
    report = generate_missing_data_report(test_session)
    assert "overall" in report
    assert "by_route" in report
    assert "by_window" in report
    assert "by_source" in report
    assert "DEL-BOM" in report["by_route"]
    assert "T+7" in report["by_window"]
