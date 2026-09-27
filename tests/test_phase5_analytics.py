import pytest
import datetime
import pandas as pd
import numpy as np

from analytics.metrics import (
    validate_route_weights,
    compute_daily_representative_prices,
    compute_base_period_prices,
    compute_relative_prices,
    calculate_weighted_geometric_apix,
    compute_daily_volatility,
    DEFAULT_ROUTE_WEIGHTS
)

def test_route_weights_validation():
    """Verify route weight validation enforces sum = 1.0 and non-negativity."""
    valid_weights = {"DEL-BOM": 0.5, "DEL-BLR": 0.5}
    assert validate_route_weights(valid_weights) is True

    # Error: Does not sum to 1.0
    with pytest.raises(ValueError):
        validate_route_weights({"DEL-BOM": 0.4, "DEL-BLR": 0.5})

    # Error: Negative weight
    with pytest.raises(ValueError):
        validate_route_weights({"DEL-BOM": 1.2, "DEL-BLR": -0.2})

def test_daily_representative_price_median():
    """Verify daily representative price calculates median and excludes duplicates."""
    df_raw = pd.DataFrame([
        # Day 1 DEL-BOM T+7: prices 4000, 5000, 6000 -> median 5000
        {"collected_at": "2026-09-01T10:00:00", "origin": "DEL", "destination": "BOM", "advance_window_days": 7, "total_fare": 4000.0, "base_fare": 3000.0, "taxes": 800.0, "mandatory_charges": 200.0, "duplicate_flag": False},
        {"collected_at": "2026-09-01T10:00:00", "origin": "DEL", "destination": "BOM", "advance_window_days": 7, "total_fare": 5000.0, "base_fare": 3800.0, "taxes": 1000.0, "mandatory_charges": 200.0, "duplicate_flag": False},
        {"collected_at": "2026-09-01T10:00:00", "origin": "DEL", "destination": "BOM", "advance_window_days": 7, "total_fare": 6000.0, "base_fare": 4500.0, "taxes": 1300.0, "mandatory_charges": 200.0, "duplicate_flag": False},
        # Duplicate record that should be ignored
        {"collected_at": "2026-09-01T10:00:00", "origin": "DEL", "destination": "BOM", "advance_window_days": 7, "total_fare": 99000.0, "base_fare": 80000.0, "taxes": 15000.0, "mandatory_charges": 4000.0, "duplicate_flag": True},
    ])

    df_medians = compute_daily_representative_prices(df_raw)
    assert len(df_medians) == 1
    row = df_medians.iloc[0]
    assert row["route"] == "DEL-BOM"
    assert row["advance_window_days"] == 7
    assert row["daily_median_price"] == 5000.0
    assert row["quote_count"] == 3

def test_base_prices_and_relative_price_ratio():
    """Verify base benchmark calculation over initial days and relative ratio R."""
    rows = []
    # 10 days of data, base period = 7 days
    for day in range(1, 11):
        dt = datetime.date(2026, 9, day)
        rows.append({
            "collection_date": dt,
            "route": "DEL-BOM",
            "advance_window_days": 7,
            "daily_median_price": 5000.0 if day <= 7 else 5500.0,
            "base_fare_avg": 3500.0,
            "taxes_avg": 1200.0,
            "charges_avg": 300.0,
            "quote_count": 4
        })

    df_medians = pd.DataFrame(rows)
    base_prices = compute_base_period_prices(df_medians, base_period_days=7)

    assert ("DEL-BOM", 7) in base_prices
    assert base_prices[("DEL-BOM", 7)] == 5000.0

    df_rel = compute_relative_prices(df_medians, base_prices)
    # Day 1-7: R = 5000/5000 = 1.0000
    assert df_rel.iloc[0]["relative_price"] == 1.0
    # Day 8-10: R = 5500/5000 = 1.1000 (+10% price increase)
    assert df_rel.iloc[7]["relative_price"] == 1.1

def test_weighted_geometric_apix_calculation():
    """
    Verify weighted geometric APIx formula:
    APIx = 100 * product( R ^ w )
    """
    weights = {"DEL-BOM": 0.6, "DEL-BLR": 0.4}
    c_date = datetime.date(2026, 9, 10)

    # Prices increased by +10% on DEL-BOM and +20% on DEL-BLR
    # Expected APIx = 100 * (1.10 ^ 0.6) * (1.20 ^ 0.4)
    expected_apix = round(100.0 * (1.10 ** 0.6) * (1.20 ** 0.4), 2)

    df_rel = pd.DataFrame([
        {"collection_date": c_date, "route": "DEL-BOM", "advance_window_days": 7, "relative_price": 1.10},
        {"collection_date": c_date, "route": "DEL-BLR", "advance_window_days": 7, "relative_price": 1.20},
    ])

    df_apix = calculate_weighted_geometric_apix(df_rel, route_weights=weights)
    assert len(df_apix) == 1
    assert bool(df_apix.iloc[0]["is_complete"]) is True
    assert df_apix.iloc[0]["apix_index"] == expected_apix

def test_apix_missing_route_basket_handling():
    """Verify that if any route in the basket is missing, APIx flags as incomplete rather than skewing."""
    weights = {"DEL-BOM": 0.5, "DEL-BLR": 0.5}
    c_date = datetime.date(2026, 9, 10)

    # Missing DEL-BLR
    df_rel = pd.DataFrame([
        {"collection_date": c_date, "route": "DEL-BOM", "advance_window_days": 7, "relative_price": 1.10},
    ])

    df_apix = calculate_weighted_geometric_apix(df_rel, route_weights=weights)
    assert len(df_apix) == 1
    assert bool(df_apix.iloc[0]["is_complete"]) is False
    assert df_apix.iloc[0]["apix_index"] is None
    assert "DEL-BLR" in df_apix.iloc[0]["missing_routes"]
