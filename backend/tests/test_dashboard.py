"""Tests for GET /api/dashboard: the Fleet Overview KPIs and live
hazard feed used to be two-thirds fabricated -- recent_events'
"Piracy Warning"/"Port Congestion" entries were permanent hardcoded
placeholders (with a static "10 minutes ago" that never actually aged),
and active_vessels was a hardcoded 42. These prove every field now
comes from a real source.
"""

import pytest
from fastapi.testclient import TestClient

from app.agents.ingestion.live_conditions_client import LiveConditionsClient
from app.main import app

client = TestClient(app)
with client:
    pass  # triggers lifespan startup once so governance agents exist

FABRICATED_STRINGS = ("Piracy Warning", "Port Congestion", "Singapore Port", "10 minutes ago", "1 hour ago")


def _fake_events(self, use_cache=True):
    return [
        {
            "event_type": "Moderate Swell & Strong Winds", "severity": "warning",
            "location": "Arabian Sea", "latitude": 18.0, "longitude": 65.0,
            "source": "open-meteo", "timestamp": "2026-01-01T00:00:00Z",
            "description": "Arabian Sea: 2.5 m significant wave height, 2.0 m swell, gusting 40 km/h.",
            "classification_reason": "Wave height 2.5 m is at or above the warning threshold of 2.5 m.",
            "conditions": {
                "wave_height_m": 2.5, "swell_height_m": 2.0, "wind_gusts_kmh": 40,
                "secondary_swell_height_m": 1.1, "ocean_current_velocity_kmh": 1.4, "visibility_m": 18000,
            },
        },
        {
            "event_type": "Slight Sea", "severity": "low",
            "location": "Gulf of Aden", "latitude": 12.65, "longitude": 47.5,
            "source": "open-meteo", "timestamp": "2026-01-01T00:00:00Z",
            "description": "Gulf of Aden: 1.0 m significant wave height, 0.8 m swell, gusting 20 km/h.",
            "classification_reason": None,
            "conditions": {"wave_height_m": 1.0, "swell_height_m": 0.8, "wind_gusts_kmh": 20},
        },
    ]


class TestDashboardIsReal:
    def test_recent_events_are_real_corridor_readings_not_fabricated_placeholders(self, monkeypatch):
        monkeypatch.setattr(LiveConditionsClient, "get_all_events", _fake_events)

        res = client.get("/api/dashboard")
        assert res.status_code == 200
        body = res.json()

        assert [e["location"] for e in body["recent_events"]] == ["Arabian Sea", "Gulf of Aden"]
        full_body = res.text
        for fabricated in FABRICATED_STRINGS:
            assert fabricated not in full_body

    def test_recent_events_carry_the_full_real_conditions_dict(self, monkeypatch):
        monkeypatch.setattr(LiveConditionsClient, "get_all_events", _fake_events)
        res = client.get("/api/dashboard")
        first = res.json()["recent_events"][0]
        # New Slice fields (secondary swell, ocean current, visibility)
        # must actually reach the response, not just the raw wave/gust
        # fields the old fabricated version implied.
        assert first["conditions"]["secondary_swell_height_m"] == 1.1
        assert first["conditions"]["ocean_current_velocity_kmh"] == 1.4
        assert first["conditions"]["visibility_m"] == 18000

    def test_active_alerts_counts_real_severities_not_a_fixed_guess(self, monkeypatch):
        monkeypatch.setattr(LiveConditionsClient, "get_all_events", _fake_events)
        res = client.get("/api/dashboard")
        # One "warning" + one "low" -- only the warning counts as an alert.
        assert res.json()["active_alerts"] == 1

    def test_no_live_data_is_reported_honestly_not_masked_with_fake_events(self, monkeypatch):
        monkeypatch.setattr(LiveConditionsClient, "get_all_events", lambda self, use_cache=True: [])
        res = client.get("/api/dashboard")
        body = res.json()
        assert body["recent_events"] == []
        assert body["average_fleet_risk"] is None
        assert body["system_status"] == "DEGRADED"

    def test_active_vessels_is_null_not_a_fabricated_count_when_ais_unconfigured(self):
        # This test environment has no AISSTREAM_API_KEY set.
        res = client.get("/api/dashboard")
        body = res.json()
        if not body["vessels_configured"]:
            assert body["active_vessels"] is None
