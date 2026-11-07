"""Input checks shared by every engine. Anything malformed raises InvalidInput."""
from datetime import date
from typing import Any, List


class InvalidInput(ValueError):
    pass


def require(cond: bool, why: str) -> None:
    if not cond:
        raise InvalidInput(why)


def is_int(value: Any) -> bool:
    return type(value) is int  # bool is a subclass of int and must not pass


def iso_date(value: Any, field: str = "date") -> date:
    require(isinstance(value, str) and len(value) == 10, f"{field} must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise InvalidInput(f"{field} is not a valid date") from None


def gbp(value: Any) -> None:
    require(value == "GBP", "currency must be GBP; mixed currencies are refused")


def unique_ids(rows: Any) -> List[dict]:
    require(isinstance(rows, list), "records must be a list")
    seen = set()
    for row in rows:
        require(isinstance(row, dict), "each record must be an object")
        rid = row.get("id")
        require(isinstance(rid, str) and rid != "", "each record needs a nonempty string id")
        require(rid not in seen, "duplicate id")
        seen.add(rid)
    return rows
