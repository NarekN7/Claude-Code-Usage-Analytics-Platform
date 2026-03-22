"""
Session analytics: duration distribution and sessions over time.
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
    Render session duration and time-series charts.

    Returns:
        None
    """
    params = st.session_state.get("query_params") or {}
    try:
        data = fetch_json("/sessions", params=params)
    except (httpx.HTTPError, httpx.RequestError) as exc:
        logger.error("Failed to load /sessions: %s", exc, exc_info=True)
        st.error("Could not load session analytics from the gateway.")
        st.caption(str(exc))
        return

    st.subheader("Session duration distribution")
    buckets = data.get("session_duration_buckets") or []
    if buckets:
        dfb = pd.DataFrame(buckets)
        fig = px.bar(dfb, x="bucket", y="session_count")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No session duration data (rebuild sessions after ingest).")

    st.subheader("Sessions started per day")
    by_day = data.get("sessions_by_day") or []
    if by_day:
        dfs = pd.DataFrame(by_day)
        if "day" in dfs.columns:
            dfs["day"] = pd.to_datetime(dfs["day"])
        fig2 = px.line(dfs, x="day", y="session_count", markers=True)
        fig2.update_layout(height=400)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No sessions-by-day series.")
