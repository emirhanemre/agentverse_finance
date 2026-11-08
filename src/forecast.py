"""Open-Meteo forecasts with explicit origin, coordinates, units and stale-cache labels."""
from __future__ import annotations
import datetime as dt
import math
import requests
from src.paper_execution import utc_now_iso

URL = 'https://api.open-meteo.com/v1/forecast'


def retrieve_forecast(profile, cached=None, allow_live=True):
    coords = {k: profile[k] for k in ('latitude', 'longitude')}
    if allow_live:
        try:
            response = requests.get(URL, params={**coords, 'timezone': 'Europe/London', 'forecast_days': 14,
                'daily': 'temperature_2m_max,temperature_2m_min,precipitation_sum,rain_sum,wind_speed_10m_max,sunshine_duration,precipitation_probability_max',
                'temperature_unit': 'celsius', 'wind_speed_unit': 'kmh', 'precipitation_unit': 'mm'}, timeout=10)
            response.raise_for_status()
            raw = response.json()['daily']
            days = []
            for i, date in enumerate(raw['time']):
                row = {k: raw[k][i] for k in ('temperature_2m_max','temperature_2m_min','precipitation_sum','rain_sum','wind_speed_10m_max','sunshine_duration')}
                if any(v is None or not math.isfinite(float(v)) for v in row.values()):
                    continue
                days.append({'date': date, 'temp_max_c': row['temperature_2m_max'],
                    'temp_min_c': row['temperature_2m_min'], 'temp_mean_c': (row['temperature_2m_max']+row['temperature_2m_min'])/2,
                    'rain_mm': row['rain_sum'], 'precipitation_mm': row['precipitation_sum'],
                    'wind_max_kmh': row['wind_speed_10m_max'], 'sunshine_hours': round(row['sunshine_duration']/3600, 3),
                    'precipitation_probability_max': raw.get('precipitation_probability_max', [None]*len(raw['time']))[i]})
            if not days:
                raise ValueError('No complete forecast days')
            return {'origin': 'current_forecast', 'source': 'Open-Meteo', 'source_url': URL,
                'retrieved_at': utc_now_iso(), 'timezone': 'Europe/London', 'coordinates': coords,
                'units': {'temperature': '°C', 'rain': 'mm', 'wind': 'km/h', 'sunshine': 'h'},
                'horizon_start': days[0]['date'], 'horizon_end': days[-1]['date'], 'days': days,
                'note': 'Grid forecast at configured coordinates. Probability of precipitation is not probability of an exact contract threshold/station/window.'}
        except (requests.RequestException, ValueError, KeyError, TypeError, IndexError):
            pass
    if cached and cached.get('coordinates') == coords:
        return {**cached, 'origin': 'cached_forecast', 'note': 'Live retrieval unavailable. Cached forecast retains its original retrieval time and horizon; it may be stale.'}
    return {'origin': 'unavailable', 'source': 'Open-Meteo', 'source_url': URL, 'coordinates': coords,
        'retrieved_at': None, 'days': [], 'note': 'Live forecast unavailable and no cache for these coordinates. Use an explicit manual weather scenario.'}
