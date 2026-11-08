"""Food Standards Agency food hygiene ratings API (England, Wales, NI; Scotland's FHIS too). No key.
Open Government Licence v3.0."""
import httpx

from .. import cache

BASE = "https://api.ratings.food.gov.uk"
LICENCE = "Open Government Licence v3.0 · Food Standards Agency"
PUB_TYPE = 7843  # "Pub/bar/nightclub"


def establishments(**params) -> dict:
    params = {"pageSize": 10, **params}
    key = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    return cache.fetch("fsa", key, lambda: httpx.get(BASE + "/Establishments", params=params, timeout=20,
                                                     headers={"x-api-version": "2", "accept": "application/json"})
                       .raise_for_status().json(), source="Food Standards Agency food hygiene ratings",
                       url=f"{BASE}/Establishments?{key}", licence=LICENCE, max_age_s=7 * 86400)
