from fastapi.testclient import TestClient

from app.agents.congestion.congestion_agent import CongestionAgent
from app.agents.delay.delay_agent import DelayAgent
from app.agents.fuel.fuel_agent import FuelAgent
from app.main import app

client = TestClient(app)
with client:
    pass  # triggers the startup event once so governance tables/agents exist


def test_congestion_agent_loads_and_predicts():
    agent = CongestionAgent()
    assert agent.is_available is True

    result = agent.predict({
        "entity_type": "vessel",
        "source": "global_loitering_weekly",
        "month": 7,
        "quarter": 3,
        "events_last_4w": 3,
        "cumulative_events_to_date": 20,
    })
    assert 0.0 <= result["congestion_probability"] <= 1.0
    assert result["congestion_flag"] in (0, 1)


def test_delay_agent_loads_and_predicts():
    agent = DelayAgent()
    assert agent.is_available is True

    result = agent.predict({
        "origin_port": "PORT09",
        "destination_port": "PORT09",
        "carrier": "V44_3",
        "service_level": "CRF",
        "customer": "V555555555555555_29",
        "plant_code": "PLANT03",
        "tpt": 1,
        "unit_quantity": 500,
        "weight": 10.0,
    })
    assert 0.0 <= result["late_probability"] <= 1.0


def test_fuel_agent_loads_and_predicts():
    agent = FuelAgent()
    assert agent.is_available is True

    result = agent.predict({
        "ship_type": "Tanker Ship",
        "route_id": "Warri-Bonny",
        "fuel_type": "HFO",
        "weather_conditions": "Moderate",
        "distance": 150.0,
        "month_num": 6,
    })
    assert result["predicted_fuel_consumption"] > 0
    assert result["estimated_cost_usd"] > 0


def test_fuel_agent_unknown_category_lowers_confidence():
    agent = FuelAgent()
    known = agent.predict({
        "ship_type": "Tanker Ship", "route_id": "Warri-Bonny",
        "fuel_type": "HFO", "weather_conditions": "Moderate",
        "distance": 150.0, "month_num": 6,
    })
    unknown = agent.predict({
        "ship_type": "Container Ship", "route_id": "Unknown-Route",
        "fuel_type": "MGO", "weather_conditions": "Foggy",
        "distance": 150.0, "month_num": 6,
    })
    assert unknown["confidence"] < known["confidence"]
    assert unknown["estimated_cost_usd"] is None  # unrecognized fuel_type has no reference price


def test_congestion_predict_endpoint_returns_completed():
    response = client.post("/api/congestion/predict", json={
        "entity_type": "vessel",
        "source": "global_loitering_weekly",
        "month": 7,
        "quarter": 3,
        "events_last_4w": 3,
        "cumulative_events_to_date": 20,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("COMPLETED", "PENDING_APPROVAL")


def test_delay_predict_endpoint_returns_completed():
    response = client.post("/api/delay/predict", json={
        "origin_port": "PORT09", "destination_port": "PORT09",
        "carrier": "V44_3", "service_level": "CRF",
        "customer": "V555555555555555_29", "plant_code": "PLANT03",
        "tpt": 1, "unit_quantity": 500, "weight": 10.0,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("COMPLETED", "PENDING_APPROVAL")


def test_fuel_predict_endpoint_returns_completed():
    response = client.post("/api/fuel/predict", json={
        "ship_type": "Tanker Ship", "route_id": "Warri-Bonny",
        "fuel_type": "HFO", "weather_conditions": "Moderate",
        "distance": 150.0, "month_num": 6,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("COMPLETED", "PENDING_APPROVAL")
