"""One place for paths, model IDs and env. Keys are read from the environment only."""
import os
from pathlib import Path

from . import REPO

DATA = REPO / "data"
FIXTURES = REPO / "fixtures"
RECORDED = FIXTURES / "recorded"  # committed, licence permitting
CACHE = FIXTURES / "cache"  # gitignored
RUNS = FIXTURES / "runs"
DB_PATH = Path(os.environ.get("PUBHEDGE_DB", REPO / "services" / "agents" / "pubhedge.db"))

# Pinned model IDs (listed via the Gemini API, see docs/data-sources.md).
MODEL_REASONING = os.environ.get("PUBHEDGE_MODEL_REASONING", "gemini-4-argon")
MODEL_FAST = os.environ.get("PUBHEDGE_MODEL_FAST", "gemini-3.8-flash")

# Rough dev budget guard, USD.
SPEND_CAP_USD = float(os.environ.get("PUBHEDGE_SPEND_CAP_USD", "8"))


def load_env() -> None:
    """Load <repo>/.env.local into os.environ without overriding what is set."""
    path = REPO / ".env.local"
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    # AI Studio only: never let ADK route to Vertex because GOOGLE_CLOUD_PROJECT is set.
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"
    if os.environ.get("GEMINI_API_KEY"):
        os.environ.setdefault("GOOGLE_API_KEY", os.environ.pop("GEMINI_API_KEY"))  # one key var, no SDK warning
    sk = os.environ.get("STRIPE_SECRET_KEY", "")
    if sk.startswith(("sk_live_", "rk_live_")):
        os.environ.pop("STRIPE_SECRET_KEY")  # hard rule: test mode only


def offline() -> bool:
    """REPLAY/offline mode: no live API or model calls (check.sh sets this)."""
    return os.environ.get("PUBHEDGE_OFFLINE") == "1"
