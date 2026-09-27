import pytest
from fastapi.testclient import TestClient
from api.main import app

@pytest.fixture(scope="module")
def client():
    """Provides a TestClient instance for testing FastAPI endpoints."""
    with TestClient(app) as test_client:
        yield test_client

def test_api_root_endpoint(client):
    """Verify root health check endpoint returns 200 and metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ONLINE"
    assert "documentation" in data
    assert "/docs" in data["documentation"]

def test_api_summary_endpoint(client):
    """Verify system summary KPI endpoint returns 200 and schema."""
    response = client.get("/api/v1/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["system_status"] == "HEALTHY"
    assert "total_quotes" in data
    assert "clean_quotes" in data
    assert data["total_quotes"] >= data["clean_quotes"]

def test_api_quotes_latest_endpoint(client):
    """Verify latest quotes endpoint with filtering."""
    # Test without filters
    response = client.get("/api/v1/quotes/latest?limit=10")
    assert response.status_code == 200
    quotes = response.json()
    assert isinstance(quotes, list)
    assert len(quotes) <= 10

    if quotes:
        q = quotes[0]
        assert "route" in q
        assert "total_fare" in q
        assert q["total_fare"] > 0
        assert q["currency"] == "INR"

    # Test with route filter
    response_del_bom = client.get("/api/v1/quotes/latest?route=DEL-BOM&limit=5")
    assert response_del_bom.status_code == 200
    del_bom_quotes = response_del_bom.json()
    for q in del_bom_quotes:
        assert q["route"] == "DEL-BOM"

def test_api_apix_trends_endpoint(client):
    """Verify APIx trends time series endpoint."""
    response = client.get("/api/v1/apix/trends?window=7")
    assert response.status_code == 200
    trends = response.json()
    assert isinstance(trends, list)
    if trends:
        item = trends[0]
        assert item["advance_window_days"] == 7
        assert "apix_index" in item

def test_api_daily_medians_endpoint(client):
    """Verify daily representative median prices endpoint."""
    response = client.get("/api/v1/prices/daily-medians?route=DEL-BOM&window=7")
    assert response.status_code == 200
    medians = response.json()
    assert isinstance(medians, list)
    for m in medians:
        assert m["route"] == "DEL-BOM"
        assert m["advance_window_days"] == 7
        assert m["daily_median_price"] > 0

def test_api_collection_runs_endpoint(client):
    """Verify collection runs audit trail endpoint."""
    response = client.get("/api/v1/runs?limit=5")
    assert response.status_code == 200
    runs = response.json()
    assert isinstance(runs, list)
    if runs:
        r = runs[0]
        assert "status" in r
        assert "source_name" in r

def test_api_source_health_endpoint(client):
    """Verify source health and circuit breaker status endpoint."""
    response = client.get("/api/v1/source-health")
    assert response.status_code == 200
    health = response.json()
    assert isinstance(health, list)
    if health:
        h = health[0]
        assert "source_name" in h
        assert "status" in h
        assert "captcha_count" in h
