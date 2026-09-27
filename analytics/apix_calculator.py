import logging
import pandas as pd
from typing import Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from database.connection import get_engine, get_session_maker
from analytics.metrics import (
    DEFAULT_ROUTE_WEIGHTS,
    compute_daily_representative_prices,
    compute_base_period_prices,
    compute_relative_prices,
    calculate_weighted_geometric_apix,
    compute_daily_volatility,
)

logger = logging.getLogger("apix.analytics.calculator")

class APIxEngine:
    """
    High-level analytics service that orchestrates:
    - Daily representative price calculations
    - Base benchmark computation
    - Weighted geometric APIx index generation
    - Heatmaps and comparative breakdowns
    """
    def __init__(self, session: Optional[Session] = None):
        self.session = session
        self._df_quotes = None
        self._df_medians = None
        self._base_prices = None
        self._df_relative = None
        self._df_apix = None

    def _fetch_quotes(self) -> pd.DataFrame:
        """Loads clean, non-duplicate quotes from the database."""
        engine = get_engine()
        query = text("""
            SELECT 
                id,
                source_name,
                source_type,
                collected_at,
                origin,
                destination,
                origin || '-' || destination AS route,
                travel_date,
                advance_window_days,
                airline_code,
                airline_name,
                flight_number,
                stop_count,
                fare_class,
                base_fare,
                taxes,
                mandatory_charges,
                total_fare,
                currency,
                duplicate_flag,
                outlier_flag
            FROM fare_quotes
            WHERE total_fare > 0
            ORDER BY collected_at ASC
        """)
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        return df

    def get_quotes_dataframe(self) -> pd.DataFrame:
        if self._df_quotes is None:
            self._df_quotes = self._fetch_quotes()
        return self._df_quotes

    def get_daily_medians(self) -> pd.DataFrame:
        if self._df_medians is None:
            df_quotes = self.get_quotes_dataframe()
            self._df_medians = compute_daily_representative_prices(df_quotes)
        return self._df_medians

    def get_base_prices(self, base_period_days: int = 7) -> Dict[tuple, float]:
        if self._base_prices is None:
            df_medians = self.get_daily_medians()
            self._base_prices = compute_base_period_prices(df_medians, base_period_days=base_period_days)
        return self._base_prices

    def get_relative_prices(self) -> pd.DataFrame:
        if self._df_relative is None:
            df_medians = self.get_daily_medians()
            base_prices = self.get_base_prices()
            self._df_relative = compute_relative_prices(df_medians, base_prices)
        return self._df_relative

    def get_apix_time_series(self, route_weights: Optional[Dict[str, float]] = None) -> pd.DataFrame:
        """Calculates APIx index series with rolling volatility."""
        df_relative = self.get_relative_prices()
        df_apix = calculate_weighted_geometric_apix(df_relative, route_weights=route_weights)
        df_apix_with_vol = compute_daily_volatility(df_apix)
        return df_apix_with_vol

    def get_route_window_heatmap_matrix(self) -> pd.DataFrame:
        """
        Returns a pivot matrix of Route (rows) x Advance Window (columns)
        with the latest representative median prices for heatmap display.
        """
        df_medians = self.get_daily_medians()
        if df_medians.empty:
            return pd.DataFrame()

        # Get latest collection date
        latest_date = df_medians["collection_date"].max()
        latest_subset = df_medians[df_medians["collection_date"] == latest_date]

        pivot = latest_subset.pivot(
            index="route",
            columns="advance_window_days",
            values="daily_median_price"
        )
        # Rename columns to T+1, T+7, etc.
        pivot.columns = [f"T+{col}" for col in pivot.columns]
        return pivot

    def get_airline_comparison(self) -> pd.DataFrame:
        """Compares median prices and volume across airlines for clean quotes."""
        df = self.get_quotes_dataframe()
        if df.empty:
            return pd.DataFrame()

        clean_df = df[df["duplicate_flag"] == False]
        airline_summary = (
            clean_df.groupby(["airline_name", "airline_code"])
            .agg(
                median_fare=("total_fare", "median"),
                avg_fare=("total_fare", "mean"),
                quote_count=("total_fare", "count"),
                avg_base_fare=("base_fare", "mean"),
                avg_taxes=("taxes", "mean")
            )
            .reset_index()
            .sort_values(by="median_fare")
        )
        return airline_summary

    def get_fare_composition_summary(self) -> pd.DataFrame:
        """Returns the breakdown of Base Fare vs Taxes vs Charges over time."""
        df_medians = self.get_daily_medians()
        if df_medians.empty:
            return pd.DataFrame()

        summary = (
            df_medians.groupby("collection_date")
            .agg(
                base_fare=("base_fare_avg", "mean"),
                taxes=("taxes_avg", "mean"),
                charges=("charges_avg", "mean"),
                total_fare=("daily_median_price", "mean")
            )
            .reset_index()
        )
        return summary
