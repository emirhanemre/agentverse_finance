import os
import tempfile

# Tests never spend API quota or model tokens: cached fixtures only, fresh DB per session.
os.environ["PUBHEDGE_OFFLINE"] = "1"
os.environ.setdefault("PUBHEDGE_DB", os.path.join(tempfile.mkdtemp(), "test.db"))
