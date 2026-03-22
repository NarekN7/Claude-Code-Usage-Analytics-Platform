"""
Claude Code Usage Analytics — Streamlit entry (assignment equivalent to app/streamlit_app.py).
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from frontend.api_client import gateway_base_url
from frontend.views import event_analytics, overview, session_analytics, user_analytics

# Default date-filter window when the telemetry was generated (see claude_code_telemetry2); avoids
# Streamlit's default of "today", which excludes all historical rows.
_DEFAULT_FILTER_FROM = date(2025, 1, 1)
_DEFAULT_FILTER_TO = date(2026, 12, 31)

st.set_page_config(
    page_title="Claude Code Usage Analytics",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _sidebar() -> None:
    """Render sidebar filters (widget keys are read by ``build_query_params()`` in each page)."""
    st.sidebar.header("Filters")
    if "use_date_filter" not in st.session_state:
        st.session_state["use_date_filter"] = False
    st.sidebar.checkbox("Filter by date range (UTC)", key="use_date_filter")
    if st.session_state["use_date_filter"]:
        if "filter_date_from" not in st.session_state:
            st.session_state["filter_date_from"] = _DEFAULT_FILTER_FROM
        if "filter_date_to" not in st.session_state:
            st.session_state["filter_date_to"] = _DEFAULT_FILTER_TO
        c1, c2 = st.sidebar.columns(2)
        with c1:
            st.date_input("From", key="filter_date_from")
        with c2:
            st.date_input("To", key="filter_date_to")
        if st.sidebar.button("Reset date range (full sample window)"):
            st.session_state["filter_date_from"] = _DEFAULT_FILTER_FROM
            st.session_state["filter_date_to"] = _DEFAULT_FILTER_TO
            st.rerun()
    st.sidebar.selectbox(
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
    st.sidebar.selectbox(
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


_sidebar()
st.sidebar.caption(f"API base: `{gateway_base_url()}`")

# Callable names are all ``render``; Streamlit needs explicit ``url_path`` for uniqueness.
pages = [
    st.Page(overview.render, title="Overview", default=True),
    st.Page(user_analytics.render, title="User analytics", url_path="user-analytics"),
    st.Page(session_analytics.render, title="Session analytics", url_path="session-analytics"),
    st.Page(event_analytics.render, title="Event analytics", url_path="event-analytics"),
]

nav = st.navigation(pages)
st.sidebar.caption("Dashboard calls the API gateway only (no direct database access).")
nav.run()
