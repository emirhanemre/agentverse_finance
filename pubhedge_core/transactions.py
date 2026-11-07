"""Bank-feed checks: directed three-account payment loops and large transfers.
A loop is a reason to ask a question, not evidence of wrongdoing."""
from typing import Any, Dict, List, Set, Tuple

from .validate import gbp, is_int, iso_date, require, unique_ids


def analyse(rows: Any, large_transfer_pence: Any) -> Dict[str, Any]:
    rows = unique_ids(rows)
    require(is_int(large_transfer_pence) and large_transfer_pence >= 1,
            "large_transfer_pence must be a positive integer")
    by_pair: Dict[Tuple[str, str], List[str]] = {}
    out_edges: Dict[str, Set[str]] = {}
    total = 0
    for r in rows:
        amt = r.get("amount_pence")
        require(is_int(amt) and amt >= 1, "amount_pence must be a positive integer")
        gbp(r.get("currency"))
        iso_date(r.get("date"))
        s, t = r.get("sender"), r.get("recipient")
        require(isinstance(s, str) and s != "" and isinstance(t, str) and t != "",
                "sender and recipient must be nonempty strings")
        total += amt
        by_pair.setdefault((s, t), []).append(r["id"])
        out_edges.setdefault(s, set()).add(t)
    flagged: Set[str] = set()
    loops = []
    for a, bs in out_edges.items():
        for b in bs:
            if b == a:
                continue
            for c in out_edges.get(b, ()):
                if c in (a, b) or a not in out_edges.get(c, ()):
                    continue
                if a != min(a, b, c):
                    continue  # report each loop once, from its smallest account
                ids = by_pair[(a, b)] + by_pair[(b, c)] + by_pair[(c, a)]
                flagged.update(ids)
                loops.append({"accounts": [a, b, c], "transaction_ids": sorted(ids)})
    large = sorted(r["id"] for r in rows if r["amount_pence"] >= large_transfer_pence)
    return {
        "cycle_transaction_ids": sorted(flagged),
        "large_transfer_ids": large,
        "total_transferred_pence": total,
        "loops": sorted(loops, key=lambda x: x["accounts"]),
    }
