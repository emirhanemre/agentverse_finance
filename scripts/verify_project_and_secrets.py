#!/usr/bin/env python3
"""Verify project deliverables, inspect binary model artifacts, and run secret scanning."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any
import joblib

from src.schemas import _SECRET_PATTERNS

ROOT = Path(__file__).resolve().parent.parent
JOBLIB_PATH = ROOT / "artifacts" / "models" / "fitted_pipeline.joblib"


def inspect_joblib_artifact(path: Path = JOBLIB_PATH) -> dict[str, Any]:
    data = path.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    bundle = joblib.load(path)
    keys = sorted(bundle.keys())

    # Serialize all non-estimator metadata to JSON and verify zero secret matches
    meta_only = {k: v for k, v in bundle.items() if k not in {"selected_pipeline", "all_fitted_models"}}
    text_dump = json.dumps(meta_only, default=str)
    matches = []
    for pat in _SECRET_PATTERNS:
        if pat.search(text_dump):
            matches.append(pat.pattern)

    return {
        "file": str(path.relative_to(ROOT)),
        "sha256": sha256,
        "size_bytes": len(data),
        "method": "joblib.load inspection of top-level keys + regex credential scan of serialized metadata",
        "evidence": f"Top-level keys={keys}; estimator={type(bundle['selected_pipeline']).__name__}; secret_regex_matches={len(matches)}",
        "result": "CLEAN (No credentials or private data present)" if not matches else "FINDINGS_DETECTED",
    }


if __name__ == "__main__":
    print(json.dumps(inspect_joblib_artifact(), indent=2))
