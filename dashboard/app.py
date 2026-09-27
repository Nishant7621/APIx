import sys
import datetime
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import text

# Ensure root directory is on sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from database.connection import get_engine, get_session_maker
from analytics.apix_calculator import APIxEngine
from pipeline.missing_data_report import generate_missing_data_report

# =============================================================================
# Streamlit App Configuration
# =============================================================================
st.set_page_config(
    page_title="APIx | Airline Price Index Dashboard",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

engine = get_engine()

# =============================================================================
# Sidebar Navigation & Settings
# =============================================================================
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/airplane-take-off.png", width=64)
    st.title("APIx Monitor")
    st.caption("Local-First Airline Price Index Engine")

    st.markdown("---")
    st.subheader("⚙️ Pilot Configuration")
    st.info(
        "**Fixed Pilot Scope**\n"
        "- Routes: 6 trunk routes\n"
        "- Windows: T+1, 7, 15, 30, 45\n"
        "- Cabin: Economy, 1 Adult\n"
        "- Currency: INR (₹)\n"
        "- Base Period: First 7 days (Index=100)"
    )

    st.markdown("---")
    st.subheader("Data Provenance")
    st.success("🏷️ Mode: Synthetic Demo / Replay Feed & Permitted Adapter")
    st.caption("Live and replay observations are cryptographically tagged and strictly segregated.")

# =============================================================================
# Top Header & Status Banner
# =============================================================================
st.title("✈️ Airline Price Index (APIx) — Live Analytics")
st.markdown(
    "Monitoring fare dynamics across major Indian domestic trunk routes, tracking component costs, "
    "and calculating the weighted geometric Airline Price Index (**APIx**)."
)

# Fetch latest system status and health
with engine.connect() as conn:
    latest_run = conn.execute(
        text("SELECT completed_at, status, source_name FROM collection_runs ORDER BY id DESC LIMIT 1")
    ).fetchone()
    
    total_quotes = conn.execute(text("SELECT COUNT(*) FROM fare_quotes")).scalar() or 0
    clean_quotes = conn.execute(text("SELECT COUNT(*) FROM fare_quotes WHERE duplicate_flag = false")).scalar() or 0
    duplicate_count = conn.execute(text("SELECT COUNT(*) FROM fare_quotes WHERE duplicate_flag = true")).scalar() or 0
    outlier_count = conn.execute(text("SELECT COUNT(*) FROM fare_quotes WHERE outlier_flag = true")).scalar() or 0
    blocked_sources = conn.execute(
        text("SELECT source_name, status, captcha_count FROM source_health WHERE status = 'BLOCKED' OR captcha_count > 0")
    ).fetchall()

# CAPTCHA / Block Alert Banner
if blocked_sources:
    st.error(
        f"🚨 **CIRCUIT BREAKER ALERT**: {len(blocked_sources)} source(s) suspended due to access restrictions or CAPTCHA prompts. "
        "Strict Compliance Policy: All bypass mechanisms are disabled. Requests halted."
    )
else:
    st.success("✅ **Source Circuit Breakers**: All monitored sources HEALTHY. Zero CAPTCHA triggers or blocks detected.")

# =============================================================================
# Analytics Engine Initialization
# =============================================================================
@st.cache_data(ttl=60)
def load_analytics_data():
    calc = APIxEngine()
    df_quotes = calc.get_quotes_dataframe()
    df_apix = calc.get_apix_time_series()
    df_heatmap = calc.get_route_window_heatmap_matrix()
    df_airlines = calc.get_airline_comparison()
    df_comp = calc.get_fare_composition_summary()
    return df_quotes, df_apix, df_heatmap, df_airlines, df_comp

df_quotes, df_apix, df_heatmap, df_airlines, df_comp = load_analytics_data()

# Calculate Latest APIx & Volatility Metrics
current_apix_t7 = "N/A"
volatility_t7 = "N/A"
if not df_apix.empty:
    t7_series = df_apix[df_apix["advance_window_days"] == 7].dropna(subset=["apix_index"])
    if not t7_series.empty:
        latest_row = t7_series.iloc[-1]
        current_apix_t7 = f"{latest_row['apix_index']:.1f}"
        if pd.notna(latest_row.get("rolling_volatility")):
            volatility_t7 = f"±{latest_row['rolling_volatility']:.2f}%"

# Top Metrics Row
last_ts_str = "N/A"
if latest_run and latest_run[0]:
    try:
        last_ts_str = pd.to_datetime(latest_run[0]).strftime("%d-%b %H:%M")
    except Exception:
        last_ts_str = str(latest_run[0])[:16]

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
kpi1.metric("Latest Run Completed", last_ts_str, delta=latest_run[1] if latest_run else None)
kpi2.metric("Total Fare Quotes", f"{total_quotes:,}", help=f"Clean: {clean_quotes:,} | Duplicates: {duplicate_count}")
kpi3.metric("Current APIx (T+7)", current_apix_t7, delta=f"{float(current_apix_t7) - 100:.1f} vs Base" if current_apix_t7 != "N/A" else None)
kpi4.metric("7-Day Volatility", volatility_t7)
kpi5.metric("Data Quality Clean Rate", f"{round(clean_quotes / total_quotes * 100, 1) if total_quotes else 0}%")

st.markdown("---")

# =============================================================================
# TABBED SECTIONS FOR DEEP EXPLORATION
# =============================================================================
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📈 APIx Index Trends",
    "🌐 OTA Platforms & Aggregators",
    "🗺️ Route Pricing Heatmap",
    "🏢 Airline Benchmarks",
    "💰 Fare Cost Composition",
    "📋 Data Quality & Missing Data",
    "🩺 System Health & Circuit Breakers"
])

# -----------------------------------------------------------------------------
# TAB 1: APIx Index Trends & Multi-Source Explorer
# -----------------------------------------------------------------------------
with tab1:
    st.subheader("📈 Airfare Trends & Comparative Price Explorer")
    st.markdown(
        "Analyze daily airfare dynamics across **individual OTA platforms** (MakeMyTrip, EaseMyTrip, etc.), "
        "**individual airline carriers** (IndiGo, Air India, etc.), and the **official macro APIx economic index**."
    )

    trend_view = st.radio(
        "Choose Analysis View:",
        [
            "🌐 Individual OTA Platforms (MakeMyTrip, EaseMyTrip, Yatra, etc.)",
            "✈️ Individual Airline Carriers (IndiGo, Air India, SpiceJet, Akasa Air)",
            "📊 Macro Economic APIx Index (Base Period = 100.0)"
        ],
        horizontal=True
    )

    st.markdown("---")

    # Helper date column on df_quotes
    if not df_quotes.empty and "collection_date" not in df_quotes.columns:
        df_quotes["collection_date"] = pd.to_datetime(df_quotes["collected_at"]).dt.date

    # VIEW 1: INDIVIDUAL OTA PLATFORMS
    if trend_view.startswith("🌐"):
        all_otas = [s for s in sorted(df_quotes["source_name"].unique()) if s != "PERMITTED_EXAMPLE_FEED"]
        routes_list = ["All Trunk Routes (National Aggregate)"] + sorted(df_quotes["route"].unique())
        windows_list = ["All Advance Windows (Composite)"] + [f"T+{w} ({w} Days Out)" for w in sorted(df_quotes["advance_window_days"].unique())]

        col_o1, col_o2, col_o3 = st.columns([2, 1, 1])
        with col_o1:
            chosen_otas = st.multiselect(
                "Select OTA Platforms to Plot Individually:",
                options=all_otas,
                default=[s for s in all_otas if s in ["MakeMyTrip", "EaseMyTrip", "Yatra", "Cleartrip", "Ixigo"]],
                help="Check or uncheck individual OTAs to compare their graphs side-by-side."
            )
        with col_o2:
            ota_route_sel = st.selectbox("Route Corridor:", routes_list, key="ota_route")
        with col_o3:
            ota_win_sel = st.selectbox("Advance Window:", windows_list, key="ota_win")

        show_ota_avg = st.checkbox("Show 'Average of All OTAs' Benchmark Line", value=True)

        # Filter data
        q_ota = df_quotes.copy()
        if ota_route_sel != "All Trunk Routes (National Aggregate)":
            q_ota = q_ota[q_ota["route"] == ota_route_sel]
        if ota_win_sel != "All Advance Windows (Composite)":
            w_int = int(ota_win_sel.split()[0].replace("T+", ""))
            q_ota = q_ota[q_ota["advance_window_days"] == w_int]

        # Aggregate daily medians per OTA
        daily_ota = q_ota.groupby(["collection_date", "source_name"])["total_fare"].median().reset_index()

        # Compute Average of All OTAs
        ota_all_only = q_ota[q_ota["source_type"] == "OTA"]
        if not ota_all_only.empty:
            daily_ota_all_avg = ota_all_only.groupby("collection_date")["total_fare"].mean().reset_index()
        else:
            daily_ota_all_avg = pd.DataFrame()

        # KPI Metrics
        m1, m2, m3, m4 = st.columns(4)
        m_avg = ota_all_only["total_fare"].mean() if not ota_all_only.empty else 0
        m1.metric("Average of All OTAs", f"₹{m_avg:,.0f}" if m_avg else "N/A")

        if not ota_all_only.empty:
            plat_means = ota_all_only.groupby("source_name")["total_fare"].mean()
            m2.metric("Lowest Priced OTA", f"{plat_means.idxmin()} (₹{plat_means.min():,.0f})")
            m3.metric("Highest Priced OTA", f"{plat_means.idxmax()} (₹{plat_means.max():,.0f})")
            m4.metric("Avg Convenience Fee", f"₹{ota_all_only['mandatory_charges'].mean():,.0f}")

        # Plot Individual OTAs + All-OTA Average
        fig_o = go.Figure()
        ota_palette = {
            "MakeMyTrip": "#FF5722",
            "EaseMyTrip": "#0284C7",
            "Yatra": "#E11D48",
            "Cleartrip": "#06B6D4",
            "Ixigo": "#9333EA",
            "Direct Airline Portal": "#16A34A"
        }

        for ota in chosen_otas:
            sub = daily_ota[daily_ota["source_name"] == ota]
            if not sub.empty:
                fig_o.add_trace(go.Scatter(
                    x=pd.to_datetime(sub["collection_date"]),
                    y=sub["total_fare"],
                    mode="lines+markers",
                    name=ota,
                    line=dict(color=ota_palette.get(ota, "#64748B"), width=2.5),
                    marker=dict(size=5)
                ))

        if show_ota_avg and not daily_ota_all_avg.empty:
            fig_o.add_trace(go.Scatter(
                x=pd.to_datetime(daily_ota_all_avg["collection_date"]),
                y=daily_ota_all_avg["total_fare"],
                mode="lines",
                name="★ AVERAGE OF ALL OTAs (Benchmark)",
                line=dict(color="#F59E0B", width=4.5, dash="dash"),
                hoverinfo="x+y+name"
            ))

        fig_o.update_layout(
            height=460,
            title="Individual OTA Platform Fares vs. Average of All OTAs",
            xaxis_title="Collection Date",
            yaxis_title="Median Fare (₹ INR)",
            hovermode="x unified",
            margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_o, use_container_width=True)

    # VIEW 2: INDIVIDUAL AIRLINE CARRIERS
    elif trend_view.startswith("✈️"):
        all_carriers = sorted(df_quotes["airline_name"].dropna().unique())
        routes_list = ["All Trunk Routes (National Aggregate)"] + sorted(df_quotes["route"].unique())
        windows_list = ["All Advance Windows (Composite)"] + [f"T+{w} ({w} Days Out)" for w in sorted(df_quotes["advance_window_days"].unique())]

        col_a1, col_a2, col_a3 = st.columns([2, 1, 1])
        with col_a1:
            chosen_airlines = st.multiselect(
                "Select Airline Companies to Plot Individually:",
                options=all_carriers,
                default=all_carriers,
                help="Check or uncheck individual airlines to see each company's price trajectory."
            )
        with col_a2:
            air_route_sel = st.selectbox("Route Corridor:", routes_list, key="air_route")
        with col_a3:
            air_win_sel = st.selectbox("Advance Window:", windows_list, key="air_win")

        show_ind_avg = st.checkbox("Show 'Industry Average (All Airlines)' Benchmark Line", value=True)

        # Filter data
        q_air = df_quotes.copy()
        if air_route_sel != "All Trunk Routes (National Aggregate)":
            q_air = q_air[q_air["route"] == air_route_sel]
        if air_win_sel != "All Advance Windows (Composite)":
            w_int = int(air_win_sel.split()[0].replace("T+", ""))
            q_air = q_air[q_air["advance_window_days"] == w_int]

        # Aggregate daily medians per Airline
        daily_air = q_air.groupby(["collection_date", "airline_name"])["total_fare"].median().reset_index()

        # Compute Industry Average
        daily_air_all_avg = q_air.groupby("collection_date")["total_fare"].mean().reset_index()

        # KPI Metrics
        c1, c2, c3, c4 = st.columns(4)
        ind_avg = q_air["total_fare"].mean() if not q_air.empty else 0
        c1.metric("Industry Average Fare", f"₹{ind_avg:,.0f}" if ind_avg else "N/A")

        if not q_air.empty:
            air_means = q_air.groupby("airline_name")["total_fare"].mean()
            c2.metric("Lowest Fare Carrier", f"{air_means.idxmin()} (₹{air_means.min():,.0f})")
            c3.metric("Highest Fare Carrier", f"{air_means.idxmax()} (₹{air_means.max():,.0f})")
            spread_diff = air_means.max() - air_means.min()
            c4.metric("Carrier Price Spread", f"₹{spread_diff:,.0f}")

        # Plot Individual Airlines + Industry Average
        fig_a = go.Figure()
        air_palette = {
            "IndiGo": "#0284C7",      # Sky Blue
            "Air India": "#DC2626",    # Red
            "Akasa Air": "#EA580C",    # Orange
            "SpiceJet": "#991B1B"      # Dark Red / Maroon
        }

        for carrier in chosen_airlines:
            sub = daily_air[daily_air["airline_name"] == carrier]
            if not sub.empty:
                fig_a.add_trace(go.Scatter(
                    x=pd.to_datetime(sub["collection_date"]),
                    y=sub["total_fare"],
                    mode="lines+markers",
                    name=carrier,
                    line=dict(color=air_palette.get(carrier, "#64748B"), width=2.5),
                    marker=dict(size=5)
                ))

        if show_ind_avg and not daily_air_all_avg.empty:
            fig_a.add_trace(go.Scatter(
                x=pd.to_datetime(daily_air_all_avg["collection_date"]),
                y=daily_air_all_avg["total_fare"],
                mode="lines",
                name="★ INDUSTRY AVERAGE (All Airlines)",
                line=dict(color="#10B981", width=4.5, dash="dash"),
                hoverinfo="x+y+name"
            ))

        fig_a.update_layout(
            height=460,
            title="Individual Airline Company Fares vs. Industry Average",
            xaxis_title="Collection Date",
            yaxis_title="Median Fare (₹ INR)",
            hovermode="x unified",
            margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_a, use_container_width=True)

    # VIEW 3: MACRO ECONOMIC APIX INDEX
    else:
        if not df_apix.empty:
            available_windows = sorted(df_apix["advance_window_days"].unique())
            selected_windows = st.multiselect(
                "Select Advance Booking Windows for APIx Basket:",
                options=available_windows,
                default=[1, 7, 30],
                format_func=lambda w: f"T+{w} ({w} Days Out)"
            )

            filtered_apix = df_apix[df_apix["advance_window_days"].isin(selected_windows)].copy()

            fig_apix = go.Figure()
            colors = {1: "#EF553B", 7: "#636EFA", 15: "#00CC96", 30: "#AB63FA", 45: "#FFA15A"}

            for win in selected_windows:
                sub = filtered_apix[filtered_apix["advance_window_days"] == win]
                fig_apix.add_trace(go.Scatter(
                    x=pd.to_datetime(sub["collection_date"]),
                    y=sub["apix_index"],
                    mode="lines+markers",
                    name=f"T+{win} Index",
                    line=dict(color=colors.get(win, "#333333"), width=2.5),
                    marker=dict(size=5)
                ))

            # Baseline horizontal line at 100.0
            fig_apix.add_hline(
                y=100.0,
                line_dash="dash",
                line_color="rgba(255, 0, 0, 0.6)",
                annotation_text="Base Benchmark (100.0)",
                annotation_position="top left"
            )

            fig_apix.update_layout(
                height=450,
                title="Macro Economic Airfare Price Index (APIx) relative to Base Benchmark (100.0)",
                xaxis_title="Collection Date",
                yaxis_title="APIx Value (Base Period = 100)",
                hovermode="x unified",
                margin=dict(l=20, r=20, t=40, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_apix, use_container_width=True)
            st.caption("ℹ️ Values > 100 represent fare inflation above the base benchmark; values < 100 indicate discount periods.")
        else:
            st.info("No APIx series data available yet. Please complete a collection cycle.")

# -----------------------------------------------------------------------------
# TAB 2: OTA Platforms & Aggregators
# -----------------------------------------------------------------------------
with tab2:
    st.subheader("🌐 Online Travel Aggregator (OTA) Price Intelligence")
    st.markdown(
        "Compare fare quotations, convenience fees, and pricing spreads across major Indian OTAs "
        "(**MakeMyTrip**, **EaseMyTrip**, **Yatra**, **Cleartrip**, **Ixigo**) alongside direct airline portals."
    )

    if not df_quotes.empty:
        all_sources = sorted(df_quotes["source_name"].unique())
        routes_list = ["All Trunk Routes"] + sorted(df_quotes["route"].unique())
        windows_list = ["All Advance Windows"] + [f"T+{w} ({w} Days Out)" for w in sorted(df_quotes["advance_window_days"].unique())]

        col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
        with col_f1:
            selected_otas = st.multiselect(
                "Select OTA & Booking Portals to Compare:",
                options=all_sources,
                default=[s for s in all_sources if s in ["MakeMyTrip", "EaseMyTrip", "Yatra", "Cleartrip", "Ixigo", "Direct Airline Portal"]]
            )
        with col_f2:
            sel_route = st.selectbox("Filter Route:", routes_list)
        with col_f3:
            sel_win_label = st.selectbox("Filter Advance Window:", windows_list)

        # Filter data
        filtered_df = df_quotes.copy()
        if sel_route != "All Trunk Routes":
            filtered_df = filtered_df[filtered_df["route"] == sel_route]
        if sel_win_label != "All Advance Windows":
            win_val = int(sel_win_label.split()[0].replace("T+", ""))
            filtered_df = filtered_df[filtered_df["advance_window_days"] == win_val]

        filtered_df["collection_date"] = pd.to_datetime(filtered_df["collected_at"]).dt.date

        # Group by date and source
        ota_trends = filtered_df.groupby(["collection_date", "source_name"])["total_fare"].median().reset_index()

        # Compute Daily Average Across ALL OTAs
        ota_only_df = filtered_df[filtered_df["source_type"] == "OTA"]
        if not ota_only_df.empty:
            ota_daily_avg = ota_only_df.groupby("collection_date")["total_fare"].mean().reset_index()
            ota_daily_avg["source_name"] = "📊 AVERAGE OF ALL OTAs"
        else:
            ota_daily_avg = pd.DataFrame(columns=["collection_date", "total_fare", "source_name"])

        # Top metric cards
        k1, k2, k3, k4 = st.columns(4)
        overall_ota_mean = ota_only_df["total_fare"].mean() if not ota_only_df.empty else 0
        overall_conv_mean = ota_only_df["mandatory_charges"].mean() if not ota_only_df.empty else 0

        cheapest_platform = "N/A"
        costliest_platform = "N/A"
        if not ota_only_df.empty:
            plat_means = ota_only_df.groupby("source_name")["total_fare"].mean()
            cheapest_platform = f"{plat_means.idxmin()} (₹{plat_means.min():,.0f})"
            costliest_platform = f"{plat_means.idxmax()} (₹{plat_means.max():,.0f})"

        k1.metric("Market Average (All OTAs)", f"₹{overall_ota_mean:,.0f}" if overall_ota_mean else "N/A")
        k2.metric("Most Competitive Platform", cheapest_platform)
        k3.metric("Highest Priced Platform", costliest_platform)
        k4.metric("Avg OTA Convenience Fee", f"₹{overall_conv_mean:,.0f}" if overall_conv_mean else "₹0")

        # Interactive Graph
        fig_ota = go.Figure()

        source_colors = {
            "MakeMyTrip": "#FF5722",           # Vibrant Orange
            "EaseMyTrip": "#0284C7",           # Blue
            "Yatra": "#E11D48",                # Red
            "Cleartrip": "#06B6D4",            # Cyan
            "Ixigo": "#9333EA",                # Purple
            "Direct Airline Portal": "#16A34A"  # Green
        }

        # Traces for individual OTAs
        for src in selected_otas:
            sub = ota_trends[ota_trends["source_name"] == src]
            if not sub.empty:
                fig_ota.add_trace(go.Scatter(
                    x=pd.to_datetime(sub["collection_date"]),
                    y=sub["total_fare"],
                    mode="lines+markers",
                    name=src,
                    line=dict(color=source_colors.get(src, "#64748B"), width=2),
                    marker=dict(size=4)
                ))

        # Trace for AVERAGE OF ALL OTAs (Thick dashed gold line)
        if not ota_daily_avg.empty:
            fig_ota.add_trace(go.Scatter(
                x=pd.to_datetime(ota_daily_avg["collection_date"]),
                y=ota_daily_avg["total_fare"],
                mode="lines",
                name="★ AVERAGE OF ALL OTAs (Benchmark)",
                line=dict(color="#F59E0B", width=4, dash="dash"),
                hoverinfo="x+y+name"
            ))

        fig_ota.update_layout(
            height=460,
            title="Daily Fare Movement by OTA Platform vs. Cross-OTA Average",
            xaxis_title="Collection Date",
            yaxis_title="Median Fare (₹ INR)",
            hovermode="x unified",
            margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_ota, use_container_width=True)

        st.markdown("---")
        bar_col, tab_col = st.columns([1, 1])

        with bar_col:
            st.markdown("**Platform Price Spread vs. All-OTA Average (%)**")
            summary_plat = filtered_df.groupby("source_name").agg(
                avg_fare=("total_fare", "mean"),
                avg_base=("base_fare", "mean"),
                avg_fee=("mandatory_charges", "mean"),
                count=("id", "count")
            ).reset_index()

            if overall_ota_mean > 0:
                summary_plat["pct_vs_avg"] = ((summary_plat["avg_fare"] - overall_ota_mean) / overall_ota_mean) * 100
            else:
                summary_plat["pct_vs_avg"] = 0.0

            fig_bar = px.bar(
                summary_plat,
                x="source_name",
                y="pct_vs_avg",
                color="pct_vs_avg",
                color_continuous_scale="RdYlGn_r",
                text="pct_vs_avg",
                labels={"source_name": "Platform", "pct_vs_avg": "Spread vs OTA Avg (%)"}
            )
            fig_bar.update_traces(texttemplate='%{text:+.1f}%', textposition='outside')
            fig_bar.update_layout(height=340, margin=dict(l=20, r=20, t=20, b=20), showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)

        with tab_col:
            st.markdown("**Platform Fee Structure & Sample Distribution**")
            styled_summary = summary_plat[["source_name", "count", "avg_fare", "avg_fee", "pct_vs_avg"]].copy()
            styled_summary.columns = ["Platform", "Quotes Count", "Avg Total Fare", "Convenience Fee", "Spread vs Avg"]
            styled_summary["Avg Total Fare"] = styled_summary["Avg Total Fare"].apply(lambda x: f"₹{x:,.0f}")
            styled_summary["Convenience Fee"] = styled_summary["Convenience Fee"].apply(lambda x: f"₹{x:,.0f}")
            styled_summary["Spread vs Avg"] = styled_summary["Spread vs Avg"].apply(lambda x: f"{x:+.2f}%")
            st.dataframe(styled_summary, use_container_width=True)
    else:
        st.info("No quote data available for OTA analysis.")

# -----------------------------------------------------------------------------
# TAB 3: Route Pricing Heatmap
# -----------------------------------------------------------------------------
with tab3:
    st.subheader("Route-Window Median Price Matrix")
    st.markdown("Shows latest representative median fares (in ₹ INR) across routes and booking windows.")

    if not df_heatmap.empty:
        fig_heat = px.imshow(
            df_heatmap,
            labels=dict(x="Advance Window", y="Route", color="Median Fare (₹)"),
            x=df_heatmap.columns,
            y=df_heatmap.index,
            text_auto=True,
            color_continuous_scale="RdYlBu_r",
            aspect="auto"
        )
        fig_heat.update_layout(height=420, margin=dict(l=30, r=30, t=30, b=30))
        st.plotly_chart(fig_heat, use_container_width=True)

        st.caption("💡 Notice the advance booking curve: T+1 fares carry peak urgency premiums, whereas T+30 and T+45 reflect advance saver fares.")
    else:
        st.info("Insufficient route observations to render heatmap.")

# -----------------------------------------------------------------------------
# TAB 4: Airline Benchmarks
# -----------------------------------------------------------------------------
with tab4:
    st.subheader("Airline Pricing Comparison & Source Distribution")

    col_air1, col_air2 = st.columns(2)

    with col_air1:
        st.markdown("**Median Fare by Operating Carrier (Economy)**")
        if not df_airlines.empty:
            fig_air = px.bar(
                df_airlines,
                x="airline_name",
                y="median_fare",
                color="airline_name",
                text="median_fare",
                labels={"airline_name": "Airline", "median_fare": "Median Fare (₹)"}
            )
            fig_air.update_traces(texttemplate='₹%{text:,.0f}', textposition='outside')
            fig_air.update_layout(height=380, showlegend=False, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_air, use_container_width=True)

    with col_air2:
        st.markdown("**Quotes Volume by Source & Type**")
        with engine.connect() as conn:
            df_src = pd.read_sql(
                text("SELECT source_name || ' (' || source_type || ')' AS source, COUNT(*) AS count FROM fare_quotes GROUP BY source_name, source_type"),
                conn
            )
        if not df_src.empty:
            fig_src = px.pie(
                df_src,
                names="source",
                values="count",
                hole=0.45,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_src.update_layout(height=380, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_src, use_container_width=True)

# -----------------------------------------------------------------------------
# TAB 5: Fare Cost Composition
# -----------------------------------------------------------------------------
with tab5:
    st.subheader("Fare Breakdown: Base Fare vs Taxes & Mandatory Charges")
    st.markdown("Tracks the evolution of fare component ratios across the 30-day monitoring timeline.")

    if not df_comp.empty:
        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(
            x=pd.to_datetime(df_comp["collection_date"]),
            y=df_comp["base_fare"],
            name="Base Airline Fare",
            marker_color="#2CA02C"
        ))
        fig_comp.add_trace(go.Bar(
            x=pd.to_datetime(df_comp["collection_date"]),
            y=df_comp["taxes"],
            name="Government Taxes (GST, UDF, PSF)",
            marker_color="#FF7F0E"
        ))
        fig_comp.add_trace(go.Bar(
            x=pd.to_datetime(df_comp["collection_date"]),
            y=df_comp["charges"],
            name="Mandatory Charges & Fees",
            marker_color="#1F77B4"
        ))

        fig_comp.update_layout(
            barmode="stack",
            height=420,
            xaxis_title="Collection Date",
            yaxis_title="Average Fare Components (₹ INR)",
            hovermode="x unified",
            margin=dict(l=20, r=20, t=30, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_comp, use_container_width=True)
    else:
        st.info("No fare breakdown data available.")

# -----------------------------------------------------------------------------
# TAB 6: Data Quality & Missing Data
# -----------------------------------------------------------------------------
with tab6:
    st.subheader("Data Quality, Deduplication, and Missing Data Audits")

    Session = get_session_maker()
    session = Session()
    try:
        report = generate_missing_data_report(session)
    finally:
        session.close()

    cov_row1, cov_row2 = st.columns(2)
    with cov_row1:
        st.markdown("**Route Completeness Matrix**")
        df_routes = pd.DataFrame.from_dict(report["by_route"], orient="index")
        st.dataframe(df_routes, use_container_width=True)

    with cov_row2:
        st.markdown("**Booking Window Completeness Matrix**")
        df_windows = pd.DataFrame.from_dict(report["by_window"], orient="index")
        st.dataframe(df_windows, use_container_width=True)

    st.markdown("---")
    st.markdown("**Inspection: Raw vs Clean Records (Deduplication & Outlier Audits)**")
    
    dq_mode = st.radio(
        "Filter View:",
        ["Clean Observations Only", "Flagged Duplicates", "Flagged Outliers (IQR / MAD)", "All Raw Records"],
        horizontal=True
    )

    dq_where = "WHERE 1=1"
    if dq_mode == "Clean Observations Only":
        dq_where += " AND duplicate_flag = false"
    elif dq_mode == "Flagged Duplicates":
        dq_where += " AND duplicate_flag = true"
    elif dq_mode == "Flagged Outliers (IQR / MAD)":
        dq_where += " AND outlier_flag = true"

    with engine.connect() as conn:
        df_dq = pd.read_sql(
            text(f"""
                SELECT 
                    id,
                    source_name,
                    source_type,
                    origin || '-' || destination AS route,
                    advance_window_days AS window,
                    airline_name,
                    flight_number,
                    stop_count,
                    travel_date,
                    total_fare,
                    currency,
                    duplicate_flag,
                    outlier_flag,
                    validation_notes
                FROM fare_quotes 
                {dq_where}
                ORDER BY collected_at DESC, id DESC 
                LIMIT 100
            """),
            conn
        )
    st.dataframe(df_dq, use_container_width=True)

# -----------------------------------------------------------------------------
# TAB 7: System Health & Circuit Breakers
# -----------------------------------------------------------------------------
with tab7:
    st.subheader("Source Reliability & Safety Circuit Breakers")
    st.markdown(
        "Monitors collection latency, success ratios, and safety status. "
        "Strict compliance enforces immediate halt on any CAPTCHA prompt or 403 access denial."
    )

    with engine.connect() as conn:
        df_health_full = pd.read_sql(
            text("""
                SELECT 
                    source_name,
                    status,
                    success_rate,
                    captcha_count,
                    http_error_count,
                    parsing_error_count,
                    average_response_time,
                    last_successful_collection,
                    checked_at
                FROM source_health
            """),
            conn
        )
    st.dataframe(df_health_full, use_container_width=True)

    st.markdown("---")
    st.subheader("Recent Collection Runs Log")
    with engine.connect() as conn:
        df_runs_recent = pd.read_sql(
            text("""
                SELECT 
                    id,
                    source_name,
                    status,
                    records_collected,
                    duration_seconds,
                    error_type,
                    started_at,
                    completed_at
                FROM collection_runs 
                ORDER BY id DESC 
                LIMIT 20
            """),
            conn
        )
    st.dataframe(df_runs_recent, use_container_width=True)
