"""Fetch England football tournament days and England/Ireland Six Nations days into data/reference/sport_days.csv.

Stdlib only. Raw downloads are cached in data/reference/raw/ (delete a file to re-fetch it).
Run from anywhere: python3 scripts/fetch_reference.py
"""
import csv
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent / "data" / "reference"
RAW = ROOT / "raw"
UK = ZoneInfo("Europe/London")
UA = "PubHedgeHackathon/0.1 (research script)"
START, END = date(2021, 1, 1), date(2026, 10, 31)
CC0 = "CC0-1.0 (openfootball)"
BYSA = "CC BY-SA 4.0 (Wikipedia contributors)"

OF = "https://raw.githubusercontent.com/openfootball/"
# (competition, url, fixed UTC offset of the file's times when the file gives none)
FOOTBALL = [
    ("Euro 2020", OF + "euro.json/master/2020/euro.json", 2),  # file times are CEST for all venues (final 21:00 = 20:00 BST)
    ("World Cup 2022", OF + "worldcup.json/master/2022/worldcup.json", 3),  # Qatar local (Eng v Iran 16:00 = 13:00 GMT)
    ("Euro 2024", OF + "euro.json/master/2024/euro.json", 2),  # Germany CEST
    ("World Cup 2026", OF + "worldcup.json/master/2026/worldcup.json", None),  # file gives "HH:MM UTC-4"
]
WIKI = "https://en.wikipedia.org/w/api.php?action=parse&prop=wikitext&format=json&formatversion=2&page="
TEAMS = {"England", "Ireland", "France", "Wales", "Scotland", "Italy"}


def fetch(url, name):
    path = RAW / name
    if not path.exists():
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            path.write_bytes(r.read())
        time.sleep(1)  # be polite to the Wikipedia API
    return path.read_text(encoding="utf-8")


def to_uk(d, hhmm, offset_hours):
    t = datetime.fromisoformat(f"{d}T{hhmm}").replace(tzinfo=timezone(timedelta(hours=offset_hours)))
    return t.astimezone(UK)


def football():
    for comp, url, fixed in FOOTBALL:
        data = json.loads(fetch(url, url.split("openfootball/")[1].replace("/master/", "_").replace("/", "_")))
        for m in data["matches"]:
            if "England" not in (m["team1"], m["team2"]):
                continue
            hhmm, *off = m["time"].split()
            offset = int(off[0][3:]) if off else fixed  # "UTC-5" -> -5
            uk = to_uk(m["date"], hhmm, offset)
            yield [uk.date().isoformat(), comp, "England", m["team2"] if m["team1"] == "England" else m["team1"],
                   uk.strftime("%H:%M"), url, CC0]


def field(box, key):
    m = re.search(rf"^\s*\|\s*{key}\s*=\s*(.*)$", box, re.M)
    return m.group(1).strip() if m else ""


def rugby():
    for year in range(2021, 2027):
        page = f"{year}_Six_Nations_Championship"
        text = json.loads(fetch(WIKI + page, f"wikipedia_{page}.json"))["parse"]["wikitext"]
        # drop boxes for postponed fixtures (2021 France v Scotland moved from 28 Feb to 26 Mar)
        boxes = [b for b in re.split(r"\{\{rugby ?box", text, flags=re.I)[1:] if not field(b, "score").startswith("Postponed")]
        assert len(boxes) == 15, f"{page}: expected 15 matches, got {len(boxes)}"
        for box in boxes:
            home, away = field(box, "id").split(" v ")  # id is "Home v Away"; team fields differ between years
            assert {home, away} <= TEAMS, box[:200]
            d = datetime.strptime(re.sub(r"\{\{.*?\}\}|<.*", "", field(box, "date")).strip(), "%d %B %Y").date()
            # e.g. "15:15 [[Central European Time|CET]] ([[UTC+1]])"; 2026 page omits the UTC part
            tm = re.match(r"(\d{1,2}:\d{2}).*?(?:UTC\s*([+−-]\d+|±0)|\|(GMT|WET|CET)\]\]\s*$)", field(box, "time"))
            off = (tm.group(2) or "").replace("−", "-").replace("±", "") or {"GMT": "0", "WET": "0", "CET": "1"}.get(tm.group(3) if tm else "")
            kick = to_uk(d, tm.group(1).zfill(5), int(off)).strftime("%H:%M") if tm and off else ""
            for team, opp in ((home, away), (away, home)):
                if team in ("England", "Ireland"):
                    yield [d.isoformat(), f"Six Nations {year}", team, opp, kick,
                           "https://en.wikipedia.org/wiki/" + page, BYSA]


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    rows = sorted(r for r in [*football(), *rugby()] if START <= date.fromisoformat(r[0]) <= END)
    with open(ROOT / "sport_days.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "competition", "team", "opponent", "kickoff_local", "source_url", "licence"])
        w.writerows(rows)
    counts = {}
    for r in rows:
        counts[r[1]] = counts.get(r[1], 0) + 1
    print(len(rows), "rows", counts)
    assert counts["Euro 2020"] == 7 and counts["Euro 2024"] == 7 and counts["World Cup 2022"] == 5
    assert all(counts[f"Six Nations {y}"] == 10 for y in range(2021, 2027))  # 5 England + 5 Ireland (Eng v Ire counted twice)


if __name__ == "__main__":
    main()
