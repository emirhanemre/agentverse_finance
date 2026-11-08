"""Seed Stripe TEST MODE with one charge per business day of synthetic demo takings.

Stripe can't backdate charges, so the business date lives in metadata.business_date.
Idempotent: Idempotency-Key per business date. Refuses any key that is not sk_test_.
  uv run --project services/agents python scripts/seed_stripe.py --days 120
"""
import argparse
import csv
import os
import time
from pathlib import Path

import httpx

from pubhedge_svc import config

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=120)
    days = ap.parse_args().days
    config.load_env()
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key.startswith("sk_test_"):
        raise SystemExit("refusing: Stripe key is not a test-mode key")
    with open(ROOT / "data" / "synthetic" / "takings_panel.csv") as f:
        rows = [r for r in csv.DictReader(f) if r["pub_id"] == "demo"][-days:]
    made = 0
    with httpx.Client(auth=(key, ""), timeout=30) as c:
        for r in rows:
            data = {"amount": int(round(float(r["takings_gbp"]) * 100)), "currency": "gbp",
                    "payment_method": "pm_card_visa", "confirm": "true",
                    "automatic_payment_methods[enabled]": "true",
                    "automatic_payment_methods[allow_redirects]": "never",
                    "description": "SYNTHETIC daily takings (demo, test mode)",
                    "metadata[business_date]": r["date"], "metadata[pub_id]": "demo",
                    "metadata[label]": "synthetic"}
            for attempt in range(5):
                resp = c.post("https://api.stripe.com/v1/payment_intents", data=data,
                              headers={"Idempotency-Key": f"pubhedge-demo-{r['date']}"})
                if resp.status_code != 429:
                    break
                time.sleep(2 ** attempt)
            resp.raise_for_status()
            if resp.json().get("livemode"):
                raise SystemExit("livemode charge returned; stopping")
            made += 1
            time.sleep(0.1)  # test mode allows 25 req/s; stay far below
    print(f"seeded {made} test charges")


if __name__ == "__main__":
    main()
