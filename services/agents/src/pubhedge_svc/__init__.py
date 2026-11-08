"""Pub Hedge agent service."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))  # shared stdlib engines live in <repo>/pubhedge_core
