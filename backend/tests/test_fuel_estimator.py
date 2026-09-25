"""Fuel estimates: the reference method, fuel energy adjustment, live-price cost
(with the price service faked) and the options the form offers."""

import pytest
from fastapi.testclient import TestClient

from app.fuel import prices as prices_module
from app.fuel.estimator import estimate
from app.fuel.prices import PriceClient
from app.fuel.reference import FUELS, SHIP_CLASSES
from app.main import app

client = TestClient(app)
with client:
    pass


class FakePrices:
    def __init__(self, table):
        self.table = table

    def bunker_price(self, fuel, hub):
        value = self.table.get(fuel)
        return {"fuel": fuel, "hub": hub, "usd_per_tonne": value, "code": "X", "as_of": "2026-09-25T00:00:00Z",
                "note": None if value else "no price"}


class NoModel:
    is_available = False


def request(**over):
    base = dict(ship_type="Bulk Carrier (Capesize)", route_id="bulk", fuel_type="HFO",
                weather_conditions="Calm", distance=3240.0, month_num=6, price_hub="SGSIN")
    return {**base, **over}


def test_reference_estimate_is_days_times_daily_burn_priced_at_the_live_price():
    # 3,240 nm at 13.5 kn = 10 days; Capesize burns 45 t/day.
    result = estimate(request(), NoModel(), FakePrices({"HFO": 700.0}))
    assert result["method"] == "reference_estimate"
    assert result["days_at_sea"] == 10.0 and result["fuel_tonnes"] == 450.0
    assert result["estimated_cost_usd"] == 315000.0
    assert result["co2_tonnes"] == round(450 * FUELS["HFO"]["co2"], 1)


def test_a_fuel_with_less_energy_per_tonne_burns_more_tonnes():
    hfo = estimate(request(), NoModel(), FakePrices({}))["fuel_tonnes"]
    methanol = estimate(request(fuel_type="Methanol"), NoModel(), FakePrices({}))["fuel_tonnes"]
    lng = estimate(request(fuel_type="LNG"), NoModel(), FakePrices({}))["fuel_tonnes"]
    assert methanol == pytest.approx(hfo * 40.2 / 19.9, rel=0.01)
    assert lng < hfo


def test_stormy_weather_costs_more_than_calm():
    calm = estimate(request(), NoModel(), FakePrices({}))["fuel_tonnes"]
    stormy = estimate(request(weather_conditions="Stormy"), NoModel(), FakePrices({}))["fuel_tonnes"]
    assert stormy == pytest.approx(calm * 1.15, rel=0.01)


def test_without_a_price_cost_is_left_out_and_confidence_drops():
    result = estimate(request(fuel_type="Methanol"), NoModel(), FakePrices({"Methanol": None}))
    assert result["estimated_cost_usd"] is None and result["confidence"] <= 0.6


@pytest.mark.parametrize("bad", [
    dict(fuel_type="Coal"), dict(ship_type="Submarine"), dict(distance=0), dict(price_hub="XXXXX"),
])
def test_unknown_inputs_are_rejected_not_guessed(bad):
    with pytest.raises(ValueError):
        estimate(request(**bad), NoModel(), FakePrices({}))


def test_in_domain_requests_use_the_trained_model():
    class Model:
        is_available = True

        def predict(self, features):
            assert features["fuel_type"] == "HFO"
            return {"predicted_fuel_consumption": 1000.0, "confidence": 0.9}

    result = estimate(request(ship_type="Tanker Ship", route_id="Warri-Bonny", distance=150.0),
                      Model(), FakePrices({"HFO": 700.0}))
    assert result["method"] == "trained_model" and result["fuel_litres"] == 1000.0
    assert result["fuel_tonnes"] == 1.0 and result["confidence"] == 0.9


def test_every_offered_ship_class_and_fuel_can_be_estimated():
    for ship in SHIP_CLASSES:
        for fuel in FUELS:
            assert estimate(request(ship_type=ship["value"], fuel_type=fuel), NoModel(), FakePrices({}))["fuel_tonnes"] > 0


def test_price_client_converts_lng_to_tonnes_and_uses_a_proxy_for_mdo(monkeypatch):
    monkeypatch.setattr(prices_module.settings, "OIL_PRICE_API", "test-key")
    seen = []

    def fake_fetch(self, code):
        seen.append(code)
        return {"price": 10.0 if code == "JKM_LNG_USD" else 900.0, "as_of": "2026-09-25T00:00:00Z"}

    monkeypatch.setattr(PriceClient, "_fetch", fake_fetch)
    pc = PriceClient()
    assert pc.bunker_price("LNG", "SGSIN")["usd_per_tonne"] == 520.0
    mdo = pc.bunker_price("MDO", "NLRTM")
    assert mdo["usd_per_tonne"] == 900.0 and "proxy" in mdo["note"] and "MGO_05S_NLRTM_USD" in seen
    assert pc.bunker_price("Methanol", "SGSIN")["usd_per_tonne"] is None


def test_a_hub_with_no_quote_falls_back_to_singapore(monkeypatch):
    monkeypatch.setattr(prices_module.settings, "OIL_PRICE_API", "test-key")
    monkeypatch.setattr(PriceClient, "_fetch",
                        lambda self, code: None if "BRSSZ" in code else {"price": 800.0, "as_of": "t"})
    result = PriceClient().bunker_price("VLSFO", "BRSSZ")
    assert result["hub"] == "SGSIN" and "Singapore" in result["note"]


def test_options_offer_the_new_ships_fuels_and_lane_routes_with_distances():
    body = client.get("/api/fuel/options").json()
    fuels = [f["value"] for f in body["fuel_types"]]
    assert fuels == ["VLSFO", "HFO", "MGO", "MDO", "LNG", "Methanol"]
    assert len(body["ship_types"]) >= 15
    lanes = [r for r in body["routes"] if r["group"] == "Shipping lanes"]
    assert len(lanes) >= 40 and all(r["distance_nm"] > 0 for r in lanes)
    assert any(r["value"] == "Warri-Bonny" for r in body["routes"])
