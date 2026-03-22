"""
Build gateway query strings from sidebar widget keys (single source of truth).

Use ``sel_practice`` / ``sel_location`` (the selectbox keys), not duplicate copies.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import streamlit as st


def build_query_params() -> dict[str, str]:
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
    practice = st.session_state.get("sel_practice")
    if practice and practice != "(all)":
        params["practice"] = practice
    location = st.session_state.get("sel_location")
    if location and location != "(all)":
        params["location"] = location
    return params
