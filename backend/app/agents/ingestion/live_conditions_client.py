"""Live marine + wind conditions from Open-Meteo.

Open-Meteo is used because it needs NO API key and no signup, so the
system has a genuinely live data path out of the box rather than one
gated behind a credential the user may not have. Two endpoints are
combined:

  - marine-api.open-meteo.com  -> wave height, swell, wave period
  - api.open-meteo.com         -> wind speed, gusts, direction

Severity is derived from observed sea state using WMO/Douglas-scale
style thresholds (see SEVERITY_THRESHOLDS), not from arbitrary numbers,
so a "critical" event corresponds to a real operational condition.

Free tier is roughly 10k requests/day, non-commercial.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

DEFAULT_TIMEOUT_SECONDS = 15

# Open-Meteo reports a 900s update interval, so anything shorter than
# that is re-fetching identical data. Without this cache every request to
# /events, /risks or /dashboard triggered a fresh 8-corridor sweep and
# took 25-29 seconds.
CACHE_TTL_SECONDS = 600
_cache: Dict[str, Any] = {"expires_at": 0.0, "events": None}
_cache_lock = threading.Lock()

# Corridors are independent, so they are fetched concurrently rather than
# one after another.
MAX_PARALLEL_REQUESTS = 8

# Real maritime chokepoints / corridors this system monitors.
MONITORED_LOCATIONS: List[Dict[str, Any]] = [
    {"name": "Strait of Hormuz", "lat": 26.57, "lon": 56.25},
    {"name": "Gulf of Aden", "lat": 12.65, "lon": 47.50},
    {"name": "Suez Canal (Gulf of Suez)", "lat": 29.35, "lon": 32.60},
    {"name": "Strait of Malacca", "lat": 2.50, "lon": 101.30},
    {"name": "Arabian Sea", "lat": 18.00, "lon": 65.00},
    {"name": "Port of Singapore", "lat": 1.26, "lon": 103.84},
    {"name": "Cape of Good Hope", "lat": -34.60, "lon": 19.50},
    {"name": "English Channel (Dover)", "lat": 50.90, "lon": 1.40},
]

# (min_wave_height_m, min_wind_gust_kmh, severity, event label)
# Bands follow the Douglas sea scale / Beaufort wind force so the
# labels correspond to genuine operational conditions.
SEVERITY_THRESHOLDS = [
    (6.0, 89.0, "critical", "Severe Storm / High Sea State"),
    (4.0, 62.0, "high", "Rough Seas & Gale Conditions"),
    (2.5, 39.0, "warning", "Moderate Swell & Strong Winds"),
    (1.25, 20.0, "low", "Slight Sea"),
]


class LiveConditionsClient:
    """Fetches current sea state and wind for monitored maritime corridors."""

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        locations: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.timeout = timeout
        self.locations = locations or MONITORED_LOCATIONS

    def fetch_conditions(self, lat: float, lon: float) -> Dict[str, Any]:
        """Current marine + wind readings for one position. Raises on failure."""
        marine = requests.get(
            MARINE_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "wave_height,wave_period,swell_wave_height,wind_wave_height",
            },
            timeout=self.timeout,
        )
        marine.raise_for_status()
        marine_now = marine.json().get("current", {})

        wind = requests.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "wind_speed_10m,wind_gusts_10m,wind_direction_10m",
            },
            timeout=self.timeout,
        )
        wind.raise_for_status()
        wind_now = wind.json().get("current", {})

        return {
            "wave_height_m": marine_now.get("wave_height"),
            "wave_period_s": marine_now.get("wave_period"),
            "swell_height_m": marine_now.get("swell_wave_height"),
            "wind_wave_height_m": marine_now.get("wind_wave_height"),
            "wind_speed_kmh": wind_now.get("wind_speed_10m"),
            "wind_gusts_kmh": wind_now.get("wind_gusts_10m"),
            "wind_direction_deg": wind_now.get("wind_direction_10m"),
            "observed_at": marine_now.get("time") or wind_now.get("time"),
        }

    def classify(self, conditions: Dict[str, Any]) -> Dict[str, str]:
        """Map observed sea state onto a severity band and event label."""
        wave = _as_float(conditions.get("wave_height_m"))
        gusts = _as_float(conditions.get("wind_gusts_kmh"))

        for min_wave, min_gust, severity, label in SEVERITY_THRESHOLDS:
            if wave >= min_wave or gusts >= min_gust:
                return {"severity": severity, "event_type": label}

        return {"severity": "info", "event_type": "Calm Conditions"}

    def _observe(self, location: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """One corridor's current reading, or None if it can't be reached."""
        try:
            conditions = self.fetch_conditions(location["lat"], location["lon"])
        except Exception:
            return None

        classified = self.classify(conditions)
        return {
            "event_type": classified["event_type"],
            "severity": classified["severity"],
            "location": location["name"],
            "latitude": location["lat"],
            "longitude": location["lon"],
            "source": "open-meteo",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "description": _describe(location["name"], conditions),
            "conditions": conditions,
        }

    def get_all_events(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Every monitored corridor's current condition, worst first.

        Cached for CACHE_TTL_SECONDS and fetched in parallel; a failed
        corridor is skipped rather than aborting the sweep.
        """
        if use_cache:
            with _cache_lock:
                if _cache["events"] is not None and time.monotonic() < _cache["expires_at"]:
                    return _cache["events"]

        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS) as pool:
            results = list(pool.map(self._observe, self.locations))

        events = [r for r in results if r is not None]

        severity_rank = {"critical": 4, "high": 3, "warning": 2, "low": 1, "info": 0}
        events.sort(
            key=lambda e: (
                severity_rank.get(e["severity"], 0),
                _as_float(e["conditions"].get("wave_height_m")),
            ),
            reverse=True,
        )

        if use_cache and events:
            with _cache_lock:
                _cache["events"] = events
                _cache["expires_at"] = time.monotonic() + CACHE_TTL_SECONDS

        return events

    def get_event(self) -> Dict[str, Any]:
        """The most severe condition across all monitored corridors — the
        one the control tower should be reasoning about."""
        events = self.get_all_events()
        if not events:
            raise RuntimeError("No live conditions could be retrieved.")
        return events[0]


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _describe(location_name: str, conditions: Dict[str, Any]) -> str:
    wave = conditions.get("wave_height_m")
    swell = conditions.get("swell_height_m")
    gusts = conditions.get("wind_gusts_kmh")
    return (
        f"{location_name}: {wave} m significant wave height, "
        f"{swell} m swell, gusting {gusts} km/h."
    )
