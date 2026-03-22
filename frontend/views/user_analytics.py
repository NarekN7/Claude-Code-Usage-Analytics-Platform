"""
User analytics: practice / level / location and top users.
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
    Render user-centric charts and tables.

    Returns:
        None
    """
    params = build_query_params()
    try:
        data = fetch_json("/users", params=params)
    except (httpx.HTTPError, httpx.RequestError) as exc:
        logger.error("Failed to load /users: %s", exc, exc_info=True)
        st.error("Could not load user analytics from the gateway.")
        st.caption(str(exc))
        return

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Tokens by practice")
        pr = data.get("token_usage_by_practice") or []
        if pr:
            dfp = pd.DataFrame(pr)
            fig = px.bar(dfp, x="practice", y="total_tokens")
            fig.update_layout(height=400, xaxis_tickangle=-35)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No practice breakdown for current filters.")

    with col2:
        st.subheader("Tokens by level")
        lv = data.get("token_usage_by_level") or []
        if lv:
            dfl = pd.DataFrame(lv)
            fig2 = px.bar(dfl, x="level", y="total_tokens")
            fig2.update_layout(height=400)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No level breakdown.")

    st.subheader("Tokens by location")
    loc = data.get("token_usage_by_location") or []
    if loc:
        dfloc = pd.DataFrame(loc)
        fig3 = px.bar(dfloc, x="location", y="total_tokens")
        fig3.update_layout(height=400)
        st.plotly_chart(fig3, use_container_width=True)

    st.subheader("Top users by tokens")
    top = data.get("top_users") or []
    if top:
        st.dataframe(pd.DataFrame(top), use_container_width=True, hide_index=True)
    else:
        st.info("No user ranking data.")
