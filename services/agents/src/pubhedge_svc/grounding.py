"""Grounding check: every number in a model narration must appear in that run's tool
outputs (allowing for formatting: £, commas, %, rounding, pence vs pounds). Sentences
with ungrounded numbers are removed and the narration is flagged."""
import re

NUM = re.compile(r"(?<![\w.])[-−]?£?\d[\d,]*(?:\.\d+)?(?:%|mm|°C|k)?")


def _values(obj, out):
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.add(float(obj))
    elif isinstance(obj, str):
        for m in NUM.findall(obj):
            v = _parse(m)
            if v is not None:
                out.add(v)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k != "receipt_id":
                _values(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _values(v, out)


def _parse(tok: str):
    t = tok.replace("−", "-").replace("£", "").replace(",", "")
    mult = 1000.0 if t.endswith("k") else 1.0
    t = re.sub(r"(%|mm|°C|k)$", "", t)
    try:
        return float(t) * mult
    except ValueError:
        return None


def allowed(outputs) -> set:
    base: set = set()
    _values(outputs, base)
    out = set()
    for v in base:
        for x in (v, abs(v), v * 100, abs(v) * 100, v / 100, abs(v) / 100):
            out.add(x)
    return out


def grounded(value: float, pool: set) -> bool:
    for p in pool:
        if abs(p - value) <= max(0.5, abs(p) * 0.005):
            return True
        if abs(value) >= 1000 and abs(p - value) <= abs(p) * 0.05 and value % 100 == 0:
            return True  # "£1,800" style rounding of a tool value
    return False


def check(narration: str, outputs) -> dict:
    pool = allowed(outputs)
    kept_lines, dropped, numbers = [], [], []
    for line in narration.strip().splitlines():
        kept = _check_line(line, pool, dropped, numbers)
        if kept:
            kept_lines.append(kept)
    return {"text": "\n".join(kept_lines), "numbers": numbers,
            "ungrounded": [n["text"] for n in numbers if not n["grounded"]], "dropped_sentences": dropped,
            "ok": not dropped}


def _check_line(line, pool, dropped, numbers) -> str:
    kept = []
    for s in re.split(r"(?<=[.!?])\s+", line.strip()):
        bad = []
        for m in NUM.findall(s):
            v = _parse(m)
            if v is None:
                continue
            ok = grounded(v, pool)
            numbers.append({"text": m, "grounded": ok})
            if not ok:
                bad.append(m)
        (dropped if bad else kept).append(s)
    return " ".join(kept)
