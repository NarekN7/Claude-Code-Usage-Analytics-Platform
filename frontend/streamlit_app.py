"""
Claude Code Usage Analytics — Streamlit entry (assignment equivalent to app/streamlit_app.py).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import streamlit as st

from frontend.views import event_analytics, overview, session_analytics, user_analytics

st.set_page_config(
    page_title="Claude Code Usage Analytics",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _build_query_params() -> dict[str, str]:
    """
    Build query string parameters for gateway APIs from sidebar selections.

    Returns:
        dict[str, str]: ISO8601 dates and optional dimension filters.
    """
    params: dict[str, str] = {}
    if st.session_state.get("use_date_filter"):
        d_from = st.session_state.get("filter_date_from")
        d_to = st.session_state.get("filter_date_to")
        if d_from is not None:
            dt0 = datetime.combine(d_from, datetime.min.time(), tzinfo=timezone.utc)
            params["date_from"] = dt0.isoformat()
        if d_to is not None:
            dt1 = datetime.combine(d_to + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
            params["date_to"] = dt1.isoformat()
    practice = st.session_state.get("filter_practice")
    if practice and practice != "(all)":
        params["practice"] = practice
    location = st.session_state.get("filter_location")
    if location and location != "(all)":
        params["location"] = location
    return params


def _sidebar() -> None:
    """
    Render sidebar filters and persist query params in session state.

    Returns:
        None
    """
    st.sidebar.header("Filters")
    st.sidebar.checkbox(
        "Filter by date range (UTC)",
        value=st.session_state.get("use_date_filter", False),
        key="use_date_filter",
    )
    if st.session_state["use_date_filter"]:
        c1, c2 = st.sidebar.columns(2)
        with c1:
            st.date_input("From", key="filter_date_from")
        with c2:
            st.date_input("To", key="filter_date_to")
    st.session_state["filter_practice"] = st.sidebar.selectbox(
        "Practice",
        options=[
            "(all)",
            "Platform Engineering",
            "Data Engineering",
            "ML Engineering",
            "Backend Engineering",
            "Frontend Engineering",
        ],
        index=0,
        key="sel_practice",
    )
    st.session_state["filter_location"] = st.sidebar.selectbox(
        "Location",
        options=[
            "(all)",
            "United States",
            "Germany",
            "United Kingdom",
            "Poland",
            "Canada",
        ],
        index=0,
        key="sel_location",
    )
    st.session_state["query_params"] = _build_query_params()


_sidebar()

pages = [
    st.Page(overview.render, title="Overview", default=True),
    st.Page(user_analytics.render, title="User analytics"),
    st.Page(session_analytics.render, title="Session analytics"),
    st.Page(event_analytics.render, title="Event analytics"),
]

nav = st.navigation(pages)
st.sidebar.caption("Dashboard calls the API gateway only (no direct database access).")
nav.run()
