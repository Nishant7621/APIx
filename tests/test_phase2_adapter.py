import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.models import CollectionRun, RawResponse, FareQuote, SourceHealth
from collector.base_adapter import BaseFlightAdapter, RawFetchResult
from collector.example_adapter import ExamplePermittedAdapter

@pytest.fixture
def test_session():
    """Provides an isolated in-memory SQLite session for tests."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_adapter_successful_collection_del_bom_t7(test_session):
    """
    Test Phase 2 requirements:
    Adapter must support DEL-BOM, T+7, and save 1 raw response and normalized quotes.
    """
    adapter = ExamplePermittedAdapter()
    result = adapter.collect(origin="DEL", destination="BOM", advance_window_days=7, session=test_session)

    assert result["status"] == "SUCCESS"
    assert result["records_collected"] == 4
    assert result["raw_response_id"] is not None
    assert len(result["payload_hash"]) == 64

    # Verify CollectionRun
    run = test_session.query(CollectionRun).filter_by(id=result["run_id"]).first()
    assert run is not None
    assert run.status == "SUCCESS"
    assert run.records_collected == 4

    # Verify RawResponse (exactly 1)
    raw_responses = test_session.query(RawResponse).filter_by(collection_run_id=run.id).all()
    assert len(raw_responses) == 1
    raw = raw_responses[0]
    assert raw.origin == "DEL"
    assert raw.destination == "BOM"
    assert raw.advance_window_days == 7

    # Verify FareQuotes (normalized, direct vs connecting, INR)
    quotes = test_session.query(FareQuote).filter_by(collection_run_id=run.id).all()
    assert len(quotes) == 4

    direct_flights = [q for q in quotes if q.stop_count == 0]
    connecting_flights = [q for q in quotes if q.stop_count > 0]
    assert len(direct_flights) == 3   # 6E, AI, QP
    assert len(connecting_flights) == 1  # SG

    for q in quotes:
        assert q.currency == "INR"
        assert q.raw_response_id == raw.id
        assert round(q.base_fare + q.taxes + q.mandatory_charges, 2) == round(q.total_fare, 2)

    # Verify SourceHealth
    health = test_session.query(SourceHealth).filter_by(source_name=adapter.source_name).first()
    assert health is not None
    assert health.status == "HEALTHY"
    assert health.captcha_count == 0

def test_unpermitted_source_compliance_guard(test_session):
    """Verify adapter enforces permission check before collection."""
    class ForbiddenAdapter(ExamplePermittedAdapter):
        def __init__(self):
            super().__init__()
            self.is_permitted = False

    adapter = ForbiddenAdapter()
    with pytest.raises(PermissionError):
        adapter.collect(origin="DEL", destination="BOM", advance_window_days=7, session=test_session)

def test_circuit_breaker_on_captcha(test_session):
    """
    Safety Rule:
    On CAPTCHA detection, adapter must immediately halt, mark BLOCKED,
    log the failure, and NOT retry.
    """
    adapter = ExamplePermittedAdapter(simulate_circuit_breaker="CAPTCHA")
    result = adapter.collect(origin="DEL", destination="BOM", advance_window_days=7, session=test_session)

    assert result["status"] == "BLOCKED"
    assert result["records_collected"] == 0

    run = test_session.query(CollectionRun).filter_by(id=result["run_id"]).first()
    assert run.status == "BLOCKED"
    assert "CAPTCHA" in run.error_type

    health = test_session.query(SourceHealth).filter_by(source_name=adapter.source_name).first()
    assert health.status == "BLOCKED"
    assert health.captcha_count == 1

def test_circuit_breaker_on_http_403(test_session):
    """
    Safety Rule:
    On HTTP 403 Forbidden, adapter must immediately halt, mark BLOCKED,
    log the failure, and NOT retry.
    """
    adapter = ExamplePermittedAdapter(simulate_circuit_breaker="403")
    result = adapter.collect(origin="DEL", destination="BOM", advance_window_days=7, session=test_session)

    assert result["status"] == "BLOCKED"
    assert result["records_collected"] == 0

    run = test_session.query(CollectionRun).filter_by(id=result["run_id"]).first()
    assert run.status == "BLOCKED"
    assert run.error_type == "HTTP_403_FORBIDDEN"
