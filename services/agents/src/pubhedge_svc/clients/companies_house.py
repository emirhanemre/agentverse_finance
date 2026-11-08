"""Companies House public data API. Open Government Licence v3.0."""
import os

import httpx

from .. import cache

BASE = "https://api.company-information.service.gov.uk"
LICENCE = "Open Government Licence v3.0 · Contains public sector information (Companies House)"


def _get(path: str, params=None) -> dict:
    r = httpx.get(BASE + path, params=params, auth=(os.environ["COMPANIES_HOUSE_KEY"], ""), timeout=20)
    r.raise_for_status()
    return r.json()


def _fetch(path: str, params=None) -> dict:
    key = path + ("?" + "&".join(f"{k}={v}" for k, v in sorted(params.items())) if params else "")
    return cache.fetch("companies_house", key, lambda: _get(path, params), source="Companies House",
                       url=BASE + path, licence=LICENCE, max_age_s=7 * 86400)


def search(q: str) -> dict:
    return _fetch("/search/companies", {"q": q, "items_per_page": 5})


def profile(number: str) -> dict:
    return _fetch(f"/company/{number}")


def officers(number: str) -> dict:
    return _fetch(f"/company/{number}/officers")
