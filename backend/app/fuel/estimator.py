"""Fuel burn, cost and CO2 for a planned voyage.

Two methods, and the result says which one produced it:

  * trained model -- when every input is one the model was trained on (the
    Niger Delta coastal dataset), its prediction is used, in litres.
  * reference estimate -- for everything else: days at sea (distance over the
    class's service speed) x the class's typical daily burn, adjusted for
    weather and for the fuel's energy content. Reference figures, not measurements.

Cost is fuel tonnes x the live bunker price for that fuel at the chosen hub.
"""

from typing import Any, Dict

from app.fuel.reference import (
    BASE_FUEL_LHV_MJ_PER_KG, DEFAULT_HUB, FUEL_ALIASES, FUELS, HUBS, LEGACY_ROUTES,
    SHIP_BY_NAME, WEATHER_FACTORS,
)

ML_SHIPS = {"Oil Service Boat", "Fishing Trawler", "Surfer Boat", "Tanker Ship"}
ML_FUELS = {"HFO", "MGO", "Diesel"}  # "Diesel" in the training data is MGO


def normalise_fuel(name: str) -> str:
    return FUEL_ALIASES.get(name, name)


def estimate(request: Dict[str, Any], ml_agent, prices) -> Dict[str, Any]:
    fuel = normalise_fuel(request["fuel_type"])
    if fuel not in FUELS:
        raise ValueError(f"Unknown fuel type '{request['fuel_type']}'.")
    ship = SHIP_BY_NAME.get(request["ship_type"])
    if ship is None:
        raise ValueError(f"Unknown ship type '{request['ship_type']}'.")
    distance = float(request["distance"])
    if distance <= 0:
        raise ValueError("Distance must be greater than zero.")
    weather = request.get("weather_conditions", "Moderate")
    hub = request.get("price_hub") or DEFAULT_HUB
    if hub not in HUBS:
        raise ValueError(f"Unknown price hub '{hub}'.")

    days = distance / (ship["knots"] * 24)
    fuel_props = FUELS[fuel]
    assumptions = []

    in_domain = (
        request["ship_type"] in ML_SHIPS and request["route_id"] in LEGACY_ROUTES
        and request["fuel_type"] in ML_FUELS and weather in WEATHER_FACTORS
        and ml_agent is not None and ml_agent.is_available
    )
    if in_domain:
        ml_request = {**request, "fuel_type": "Diesel" if fuel == "MGO" else "HFO"}
        result = ml_agent.predict(ml_request)
        litres = result["predicted_fuel_consumption"]
        tonnes = litres * fuel_props["density"] / 1000
        method, confidence = "trained_model", result["confidence"]
        assumptions.append(
            "Predicted by the model trained on Niger Delta coastal voyages; converted from litres to tonnes at "
            f"{fuel_props['density']} kg/L."
        )
    else:
        hfo_equivalent = ship["t_per_day"] * days * WEATHER_FACTORS.get(weather, 1.0)
        tonnes = hfo_equivalent * BASE_FUEL_LHV_MJ_PER_KG / fuel_props["lhv"]
        litres = None
        method, confidence = "reference_estimate", 0.7
        assumptions += [
            f"{ship['value']}: about {ship['t_per_day']} t/day of fuel-oil equivalent at {ship['knots']} kn "
            "(typical for the class; real ships vary widely).",
            f"Weather factor {WEATHER_FACTORS.get(weather, 1.0)} for {weather.lower()} conditions (a rule-of-thumb allowance).",
            f"{fuel_props['label']} carries {fuel_props['lhv']} MJ/kg against 40.2 for fuel oil, so the same voyage "
            f"takes {BASE_FUEL_LHV_MJ_PER_KG / fuel_props['lhv']:.2f}x the tonnes.",
        ]

    price = prices.bunker_price(fuel, hub)
    cost = round(tonnes * price["usd_per_tonne"], 2) if price["usd_per_tonne"] is not None else None
    if price["usd_per_tonne"] is None:
        confidence = min(confidence, 0.6)

    return {
        "method": method,
        "ship_type": request["ship_type"],
        "fuel_type": fuel,
        "distance_nm": distance,
        "days_at_sea": round(days, 1),
        "speed_knots": ship["knots"],
        "fuel_tonnes": round(tonnes, 1),
        "fuel_litres": round(litres, 1) if litres is not None else None,
        "co2_tonnes": round(tonnes * fuel_props["co2"], 1),
        "price": price,
        "estimated_cost_usd": cost,
        "confidence": round(confidence, 2),
        "assumptions": assumptions,
    }
