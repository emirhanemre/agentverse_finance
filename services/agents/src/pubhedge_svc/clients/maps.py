"""A pub's postcode from its name: one Gemini call grounded on Google Maps. The answer is only a lead; the verifier
then checks it against the hygiene register and postcodes.io."""
import os
import re

from .. import cache
from ..config import MODEL_FAST

POSTCODE = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2})\b", re.I)


def postcode_for(pub_name: str) -> dict:
    def ask():
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"], http_options=types.HttpOptions(timeout=30_000))
        r = client.models.generate_content(
            model=MODEL_FAST,
            contents=f"What is the full UK postcode of the pub '{pub_name}'? Reply with the postcode only.",
            config=types.GenerateContentConfig(tools=[types.Tool(google_maps=types.GoogleMaps())], temperature=0))
        m = POSTCODE.search(r.text or "")
        return {"postcode": m.group(1).upper() if m else None, "answer": (r.text or "")[:200]}
    return cache.fetch("maps", pub_name.strip().lower(), ask, source="Gemini grounded on Google Maps",
                       url="https://ai.google.dev/gemini-api/docs/maps-grounding", licence="Google Maps Platform terms",
                       max_age_s=30 * 86400)
