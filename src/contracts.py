"""Evidence-based parsing for supported daily UK weather contracts.

Parse a deliberately bounded grammar; unsupported/ambiguous rules receive specific
errors. The source text and its hash remain bound to the paper approval.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import datetime as dt
import hashlib
import json
import math
import re
from urllib.parse import urlparse

from src.risk_controls import MONTH_NAME_TO_NUM

STATIONS = {
    'EGLC': ('London City Airport', 51.5053, .0553, 'Europe/London'),
    'EGLL': ('London Heathrow Airport', 51.4775, -.4614, 'Europe/London'),
    'EGCC': ('Manchester Airport', 53.3537, -2.2750, 'Europe/London'),
    'EGBB': ('Birmingham Airport', 52.4539, -1.7480, 'Europe/London'),
    'EGPH': ('Edinburgh Airport', 55.9500, -3.3725, 'Europe/London'),
    'EGPF': ('Glasgow Airport', 55.8719, -4.4331, 'Europe/London'),
}


def rules_hash(market):
    return hashlib.sha256(json.dumps({k:getattr(market,k) for k in ('condition_id','question','resolution_rules','resolution_source','outcomes','clob_token_ids')},sort_keys=True).encode()).hexdigest()


def distance_km(lat1, lon1, lat2, lon2):
    a,b=map(math.radians,(lat1,lat2));dlat=b-a;dlon=math.radians(lon2-lon1)
    return 6371*2*math.asin(min(1,math.sqrt(math.sin(dlat/2)**2+math.cos(a)*math.cos(b)*math.sin(dlon/2)**2)))


def event_date(market):
    """Read event day from the question, not the following-day source URL."""
    q=market.question
    m=re.search(r'\bon\s+(\d{4}-\d{2}-\d{2})\b',q,re.I)
    if m:
        return dt.date.fromisoformat(m[1]).isoformat()
    m=re.search(r'\bon\s+([A-Za-z]+)\s+(\d{1,2})(?:,?\s+(20\d{2}))?',q,re.I)
    if m and m[1].lower() in MONTH_NAME_TO_NUM:
        year=int(m[3] or (market.end_date or '')[:4])
        return dt.date(year,MONTH_NAME_TO_NUM[m[1].lower()],int(m[2])).isoformat()
    raise ValueError('No unambiguous event day in the contract question.')


@dataclass
class ContractSpec:
    date: str
    station: str
    station_name: str
    station_distance_km: float
    timezone: str
    metric: str
    unit: str
    lower: float | None
    upper: float | None
    lower_inclusive: bool
    upper_inclusive: bool
    rounding: str
    rules_hash: str
    source: str
    basis_note: str

    def matches(self, weather):
        value=float(weather['rain_mm' if self.metric=='precipitation_or_rainfall' else 'temp_max_c'])
        if self.unit=='F': value=value*9/5+32
        if self.rounding=='nearest_integer_half_upward': value=math.floor(value+.5)
        return ((self.lower is None or (value>=self.lower if self.lower_inclusive else value>self.lower)) and
                (self.upper is None or (value<=self.upper if self.upper_inclusive else value<self.upper)))

    def to_dict(self): return asdict(self)


def parse_contract(market, profile, max_station_distance_km=30):
    if market.outcomes != ['Yes','No'] or len(market.clob_token_ids)!=2:
        raise ValueError('Supported live contracts require an explicit Yes/No binary outcome and token mapping.')
    rules=market.resolution_rules
    q=market.question.replace('−','-').replace('–','-')
    low=rules.lower()
    codes=[code for code,(name,*_) in STATIONS.items() if re.search(r'\b'+code+r'\b',rules,re.I) or name.lower() in low]
    if len(codes)!=1:
        raise ValueError('Resolution rules must identify exactly one supported airport station (EGLC, EGLL, EGCC, EGBB, EGPH or EGPF).')
    station=codes[0];name,lat,lon,zone=STATIONS[station]
    distance=distance_km(profile['latitude'],profile['longitude'],lat,lon)
    if distance>max_station_distance_km:
        raise ValueError(f'Resolution station {station} is {distance:.1f}km from this business, beyond the configured {max_station_distance_km:g}km basis-distance limit.')
    source=market.resolution_source
    host=(urlparse(source).hostname or '').lower()
    if not any(host==d or host.endswith('.'+d) for d in ('aviationweather.gov','wunderground.com','metoffice.gov.uk')):
        raise ValueError('Resolution source is not a supported official weather source URL.')
    date=event_date(market)
    # An explicit prose date must agree with the question. Source URLs may refer
    # to retrieval on the next day and are intentionally not used for event day.
    prose=re.search(r"\bon\s+(\d{1,2})\s+([A-Za-z]{3,9})\s+['’]?(\d{2}|20\d{2})\b",rules,re.I)
    if prose and prose[2].lower() in MONTH_NAME_TO_NUM:
        year=int(prose[3]);year=year+2000 if year<100 else year
        if dt.date(year,MONTH_NAME_TO_NUM[prose[2].lower()],int(prose[1])).isoformat()!=date:
            raise ValueError('Question and resolution-rule observation dates disagree.')
    if not any(s in low for s in ('local time','europe/london')):
        raise ValueError('The observation day/timezone is not explicitly defined as local station time.')
    if re.search(r'highest temperature|daily maximum temperature',q,re.I):
        metric='daily_max_temperature';unit='F' if re.search(r'°\s*F',q,re.I) else 'C'
        if not re.search(r'°\s*[CF]',q,re.I):
            raise ValueError('Temperature unit is missing from the question.')
        if 'highest temperature' not in low and 'maximum temperature' not in low:
            raise ValueError('Rules do not define the daily maximum-temperature measurement.')
        if (unit=='C' and 'celsius' not in low and '°c' not in low) or (unit=='F' and 'fahrenheit' not in low and '°f' not in low):
            raise ValueError('Question temperature units do not agree with the resolution measurement rules.')
        if not ('nearest whole' in low and re.search(r'exactly\s+half\s+rounded\s+up\s+to\s+the\s+next\s+higher\s+whole\s+degree',low)):
            raise ValueError('The temperature rounding/tie rule is unsupported or ambiguous.')
        if host=='aviationweather.gov' and not all(s in low for s in ('routine','speci','hourly temperature remark')):
            raise ValueError('METAR rules must define routine observations, SPECI exclusion and the temperature remark.')
        m=re.search(r'be\s+(-?\d+(?:\.\d+)?)\s*°\s*[CF](?:\s+(or below|or higher))?',q,re.I)
        between=re.search(r'between\s+(-?\d+)\s*(?:and|-)\s*(-?\d+)\s*°\s*[CF]',q,re.I)
        if between: lower,upper=float(between[1]),float(between[2])
        elif m:
            value=float(m[1]);side=(m[2] or '').lower()
            lower=None if side=='or below' else value
            upper=None if side=='or higher' else value
        else: raise ValueError('Unsupported temperature bracket grammar.')
        rounding='nearest_integer_half_upward';li=ui=True
    elif re.search(r'rainfall|precipitation|\brain\b',q,re.I):
        if 'precipitation' in q.lower() and not re.search(r'rainfall|\brain\b',q,re.I):
            raise ValueError('Total precipitation can include snow; it is not interchangeable with the supported rainfall-only scenario.')
        metric='precipitation_or_rainfall';unit='mm';rounding='none';li=ui=True
        if not re.search(r'daily|24.hour|00:00.*24:00|midnight',rules,re.I):
            raise ValueError('Rainfall must have an explicit full local-day observation window.')
        m=re.search(r'(?:>=|≥)\s*(\d+(?:\.\d+)?)\s*mm|(\d+(?:\.\d+)?)\s*mm\s+or\s+(?:more|higher)',q,re.I)
        if not m: raise ValueError('Unsupported rainfall threshold grammar; explicit ≥N mm is required.')
        lower=float(m[1] or m[2]);upper=None
        rule_threshold=re.search(r'(?:>=|≥)\s*(\d+(?:\.\d+)?)\s*mm|(\d+(?:\.\d+)?)\s*mm\s+or\s+(?:more|higher)',rules,re.I)
        if not rule_threshold or float(rule_threshold[1] or rule_threshold[2]) != lower:
            raise ValueError('Rainfall threshold is not corroborated in the resolution rules.')
    else: raise ValueError('Contract is not a supported daily rainfall or maximum-temperature contract.')
    return ContractSpec(date,station,name,round(distance,2),zone,metric,unit,lower,upper,li,ui,rounding,rules_hash(market),source,
        f'{name} ({station}), {distance:.1f}km from the business. Airport observations and gridded business-location weather can diverge. Station fallback/correction clauses in the original rules still apply; no numerical basis-risk score is claimed.')


def payoff_direction(spec, adverse, reference):
    a,b=spec.matches(adverse),spec.matches(reference)
    if a==b:
        raise ValueError('This contract has the same payoff in the selected adverse and reference scenarios; it does not offset their difference.')
    return 'Yes' if a else 'No'
