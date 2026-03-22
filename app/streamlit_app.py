"""
Assignment-compatible entry path (`app/streamlit_app.py`).

The layered dashboard source lives in ``frontend/streamlit_app.py``; this shim
delegates so either path can be used with ``streamlit run``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import runpy

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_FRONTEND = _ROOT / "frontend" / "streamlit_app.py"
runpy.run_path(str(_FRONTEND), run_name="__main__")
