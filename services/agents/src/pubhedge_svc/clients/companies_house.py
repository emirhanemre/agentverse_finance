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


def psc(number: str) -> dict:
    """Who controls the company. Only the kind is kept, and the name only for a corporate controller: an individual's
    details never reach the cache or the recorded fixtures."""
    path = f"/company/{number}/persons-with-significant-control"

    def get():
        items = _get(path).get("items", [])
        return {"items": [{"kind": x.get("kind"), "ceased_on": x.get("ceased_on"),
                           **({"name": x.get("name")} if "corporate" in (x.get("kind") or "") else {})} for x in items]}
    return cache.fetch("companies_house", "psc:" + number, get, source="Companies House", url=BASE + path,
                       licence=LICENCE, max_age_s=7 * 86400)


def charges(number: str) -> dict:
    return _fetch(f"/company/{number}/charges")


def pubs_at(postcode: str) -> dict:
    """Pubs and bars (SIC 56302, 56301) whose registered office is at this postcode. 404 means none."""
    def get():
        try:
            return _get("/advanced-search/companies", {"sic_codes": "56302,56301", "location": postcode,
                                                       "company_status": "active", "size": 20})
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {"items": []}
            raise
    return cache.fetch("companies_house", "pubs_at:" + postcode, get, source="Companies House advanced search",
                       url=BASE + "/advanced-search/companies", licence=LICENCE, max_age_s=7 * 86400)
