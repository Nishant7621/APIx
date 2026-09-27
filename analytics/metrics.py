import logging
import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional, List

logger = logging.getLogger("apix.analytics.metrics")

# Default pilot route weights (Must sum to 1.0)
DEFAULT_ROUTE_WEIGHTS = {
    "DEL-BOM": 0.25,
    "DEL-BLR": 0.20,
    "BOM-BLR": 0.15,
    "DEL-CCU": 0.15,
    "BLR-HYD": 0.15,
    "MAA-DEL": 0.10,
}

def validate_route_weights(weights: Dict[str, float], tolerance: float = 1e-4) -> bool:
    """Validates that route weights are non-negative and sum to exactly 1.0."""
    total = sum(weights.values())
    if any(w < 0 for w in weights.values()):
        raise ValueError("Route weights cannot be negative.")
    if abs(total - 1.0) > tolerance:
        raise ValueError(f"Route weights must sum to 1.0, current sum is {total:.5f}.")
    return True

def compute_daily_representative_prices(df_quotes: pd.DataFrame) -> pd.DataFrame:
    """
    Computes daily representative price per route and booking window
    using the median of comparable economy quotes (excluding duplicates).
    """
    if df_quotes.empty:
        return pd.DataFrame()

    # Filter out duplicates and invalid fares
    clean_df = df_quotes[
        (df_quotes["duplicate_flag"] == False) &
        (df_quotes["total_fare"] > 0)
    ].copy()

    # Create composite route identifier if not present
    if "route" not in clean_df.columns:
        clean_df["route"] = clean_df["origin"] + "-" + clean_df["destination"]

    # Extract date part of collected_at
    if "collection_date" not in clean_df.columns:
        clean_df["collection_date"] = pd.to_datetime(clean_df["collected_at"]).dt.date

    # Group by (collection_date, route, advance_window_days)
    grouped = (
        clean_df.groupby(["collection_date", "route", "advance_window_days"])
        .agg(
            daily_median_price=("total_fare", "median"),
            daily_mean_price=("total_fare", "mean"),
            quote_count=("total_fare", "count"),
            base_fare_avg=("base_fare", "mean"),
            taxes_avg=("taxes", "mean"),
            charges_avg=("mandatory_charges", "mean")
        )
        .reset_index()
    )

    grouped["daily_median_price"] = grouped["daily_median_price"].round(2)
    return grouped

def compute_base_period_prices(
    df_daily_medians: pd.DataFrame,
    base_period_days: int = 7
) -> Dict[Tuple[str, int], float]:
    """
    Calculates base price benchmark for each (route, window)
    using the average of the daily medians over the initial 7 collection days.
    """
    if df_daily_medians.empty:
        return {}

    dates = sorted(df_daily_medians["collection_date"].unique())
    base_dates = dates[:base_period_days]

    base_subset = df_daily_medians[df_daily_medians["collection_date"].isin(base_dates)]

    base_prices = (
        base_subset.groupby(["route", "advance_window_days"])["daily_median_price"]
        .mean()
        .round(2)
        .to_dict()
    )
    return base_prices

def compute_relative_prices(
    df_daily_medians: pd.DataFrame,
    base_prices: Dict[Tuple[str, int], float]
) -> pd.DataFrame:
    """
    Calculates relative price ratio R(route, window, day) = daily_price / base_price.
    """
    df = df_daily_medians.copy()

    def get_base(row):
        key = (row["route"], int(row["advance_window_days"]))
        return base_prices.get(key, np.nan)

    df["base_price"] = df.apply(get_base, axis=1)
    df["relative_price"] = np.where(
        df["base_price"] > 0,
        df["daily_median_price"] / df["base_price"],
        np.nan
    )
    df["relative_price"] = df["relative_price"].round(4)
    return df

def calculate_weighted_geometric_apix(
    df_relative: pd.DataFrame,
    route_weights: Optional[Dict[str, float]] = None
) -> pd.DataFrame:
    """
    Calculates weighted geometric APIx index:
    APIx(window, day) = 100 * product( R(route, window, day) ^ w_route )
    Computed in log space: 100 * exp( sum( w_route * ln(R) ) ).

    Returns separate APIx series per booking window, plus composite overall APIx.
    """
    weights = route_weights or DEFAULT_ROUTE_WEIGHTS
    validate_route_weights(weights)

    if df_relative.empty:
        return pd.DataFrame()

    results = []
    routes_in_basket = list(weights.keys())

    # Calculate per (collection_date, advance_window_days)
    for (c_date, window), group in df_relative.groupby(["collection_date", "advance_window_days"]):
        group_routes = set(group["route"].unique())
        
        # Check if all routes in basket are present
        missing_routes = [r for r in routes_in_basket if r not in group_routes]
        
        if missing_routes:
            # Cannot calculate accurately if basket components are missing
            results.append({
                "collection_date": c_date,
                "advance_window_days": window,
                "apix_index": None,
                "is_complete": bool(False),
                "missing_routes": ", ".join(missing_routes),
                "notes": f"Missing data for routes: {missing_routes}"
            })
            continue

        # Weighted geometric mean calculation in log space
        log_sum = 0.0
        for route, w in weights.items():
            r_val = group[group["route"] == route]["relative_price"].values[0]
            if pd.isna(r_val) or r_val <= 0:
                log_sum = np.nan
                break
            log_sum += w * np.log(r_val)

        if np.isnan(log_sum):
            apix_val = None
        else:
            apix_val = round(float(100.0 * np.exp(log_sum)), 2)

        results.append({
            "collection_date": c_date,
            "advance_window_days": window,
            "apix_index": apix_val,
            "is_complete": bool(True),
            "missing_routes": "",
            "notes": "Calculated via weighted geometric basket"
        })

    df_apix = pd.DataFrame(results)
    if not df_apix.empty:
        df_apix = df_apix.sort_values(by=["advance_window_days", "collection_date"]).reset_index(drop=True)

    return df_apix

def compute_daily_volatility(df_apix: pd.DataFrame, window_days: int = 7) -> pd.DataFrame:
    """
    Calculates rolling price volatility (std dev of percentage daily APIx changes).
    """
    if df_apix.empty or "apix_index" not in df_apix.columns:
        return df_apix

    df = df_apix.copy()
    df["daily_change_pct"] = (
        df.groupby("advance_window_days")["apix_index"]
        .pct_change() * 100.0
    ).round(2)

    df["rolling_volatility"] = (
        df.groupby("advance_window_days")["daily_change_pct"]
        .rolling(window=window_days, min_periods=2)
        .std()
        .reset_index(level=0, drop=True)
        .round(2)
    )
    return df
