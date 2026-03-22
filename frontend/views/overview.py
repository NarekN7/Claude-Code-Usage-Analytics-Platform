"""
Overview page: KPIs and usage trends.
"""

from __future__ import annotations

import logging

import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

from frontend.api_client import fetch_json

logger = logging.getLogger(__name__)


def render() -> None:
    """
    Render the Overview page with KPIs and trend charts.

    Returns:
        None
    """
    params = st.session_state.get("query_params") or {}
    try:
        data = fetch_json("/metrics", params=params)
    except (httpx.HTTPError, httpx.RequestError) as exc:
        logger.error("Failed to load /metrics: %s", exc, exc_info=True)
        st.error("Could not load metrics from the gateway. Is the API running?")
        st.caption(str(exc))
        return

    totals = data.get("totals") or {}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Distinct users", f"{totals.get('total_users', 0):,}")
    c2.metric("Sessions (events)", f"{totals.get('total_sessions', 0):,}")
    c3.metric("Events", f"{totals.get('total_events', 0):,}")
    c4.metric("Total tokens", f"{totals.get('total_tokens', 0):,}")

    st.subheader("Token usage over time (daily)")
    by_day = data.get("usage_by_day") or []
    if by_day:
        df = pd.DataFrame(by_day)
        if "day" in df.columns:
            df["day"] = pd.to_datetime(df["day"])
        fig = px.line(df, x="day", y="total_tokens", markers=True)
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No daily usage data for the selected filters.")

    st.subheader("Tokens by hour of day (UTC)")
    by_hour = data.get("usage_by_hour") or []
    if by_hour:
        dfh = pd.DataFrame(by_hour)
        fig2 = px.bar(dfh, x="hour", y="total_tokens")
        fig2.update_layout(height=350)
        st.plotly_chart(fig2, use_container_width=True)
