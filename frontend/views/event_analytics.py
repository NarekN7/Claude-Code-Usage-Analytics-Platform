"""
Event analytics: event types and model usage.
"""

from __future__ import annotations

import logging

import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

from frontend.api_client import fetch_json
from frontend.query_params import build_query_params

logger = logging.getLogger(__name__)


def render() -> None:
    """
    Render event-type and model distribution charts.

    Returns:
        None
    """
    params = build_query_params()
    try:
        data = fetch_json("/events/summary", params=params)
    except (httpx.HTTPError, httpx.RequestError) as exc:
        logger.error("Failed to load /events/summary: %s", exc, exc_info=True)
        st.error("Could not load event analytics from the gateway.")
        st.caption(str(exc))
        return

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Event type distribution")
        et = data.get("event_type_distribution") or []
        if et:
            dfe = pd.DataFrame(et)
            fig = px.pie(dfe, names="event_type", values="event_count", hole=0.35)
            fig.update_layout(height=450)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No event types in range.")

    with col2:
        st.subheader("Model usage (events)")
        md = data.get("model_distribution") or []
        if md:
            dfm = pd.DataFrame(md)
            fig2 = px.bar(dfm, x="model", y="event_count")
            fig2.update_layout(height=450, xaxis_tickangle=-45)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No model-tagged events in range.")
