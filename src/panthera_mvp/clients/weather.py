"""Open-Meteo weather client — kickoff-hour wind/temperature/precipitation.

Keyless. Two hosts with one response shape: the forecast API (live slates,
up to ~16 days out) and the archive API (reanalysis, for backtests). Lookup
is by venue coordinates (from CFBD /venues) and the kickoff hour in UTC.
Indoor venues should skip the call entirely — the caller decides that.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

from ..timeutil import parse_utc

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
TIMEOUT = 30
HOURLY = "temperature_2m,precipitation,wind_speed_10m,wind_gusts_10m"


@dataclass
class KickoffWeather:
    temperature_f: float | None
    precipitation_in: float | None
    wind_mph: float | None
    gust_mph: float | None


def parse_hourly(payload: dict, kickoff_utc: str) -> KickoffWeather | None:
    """Pick the hourly row for the kickoff hour (floored to the hour, UTC)."""
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    target = parse_utc(kickoff_utc).strftime("%Y-%m-%dT%H:00")
    if target not in times:
        return None
    i = times.index(target)

    def _val(key: str) -> float | None:
        vals = hourly.get(key) or []
        return vals[i] if i < len(vals) else None

    return KickoffWeather(
        temperature_f=_val("temperature_2m"),
        precipitation_in=_val("precipitation"),
        wind_mph=_val("wind_speed_10m"),
        gust_mph=_val("wind_gusts_10m"),
    )


def get_kickoff_weather(
    latitude: float,
    longitude: float,
    kickoff_utc: str,
    historical: bool = False,
    session: requests.Session | None = None,
) -> KickoffWeather | None:
    day = parse_utc(kickoff_utc).strftime("%Y-%m-%d")
    sess = session or requests.Session()
    resp = sess.get(
        ARCHIVE_URL if historical else FORECAST_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "hourly": HOURLY,
            "start_date": day,
            "end_date": day,
            "timezone": "UTC",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return parse_hourly(resp.json(), kickoff_utc)
