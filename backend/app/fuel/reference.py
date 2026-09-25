"""Reference data for fuel estimates: what each fuel is, what a ship class
burns, and where bunker prices are quoted.

None of this is measured here. Fuel properties are the standard published
values (IMO/ISO lower calorific values and CO2 emission factors). Ship-class
burn rates are approximate typical figures for a ship of that class at its
service speed, rounded from public industry references; real ships vary by
tens of percent with age, hull condition, trim and load. That is why an
estimate for a class of ship is labelled a reference estimate, not a
prediction of one particular vessel.
"""

from typing import Dict, List, Optional

# Energy content is the point of comparing fuels: a tonne of methanol
# carries under half the energy of a tonne of fuel oil, so the same voyage
# burns more than twice the tonnes.
BASE_FUEL_LHV_MJ_PER_KG = 40.2  # heavy fuel oil; burn rates below are quoted as HFO-equivalent

FUELS: Dict[str, Dict] = {
    "VLSFO": {"label": "VLSFO (0.5% sulphur)", "lhv": 41.0, "co2": 3.151, "density": 0.95},
    "HFO": {"label": "HSFO / HFO (high sulphur)", "lhv": 40.2, "co2": 3.114, "density": 0.99},
    "MGO": {"label": "MGO (marine gas oil)", "lhv": 42.7, "co2": 3.206, "density": 0.85},
    "MDO": {"label": "MDO (marine diesel oil)", "lhv": 42.7, "co2": 3.206, "density": 0.89},
    "LNG": {"label": "LNG", "lhv": 49.5, "co2": 2.750, "density": 0.45},
    "Methanol": {"label": "Methanol", "lhv": 19.9, "co2": 1.375, "density": 0.79},
}
# Older name used by the trained model's data.
FUEL_ALIASES = {"Diesel": "MGO"}

# Live-price source per fuel on oilpriceapi.com. `{hub}` is a UN/LOCODE bunkering hub.
PRICE_CODES: Dict[str, Optional[str]] = {
    "VLSFO": "VLSFO_{hub}_USD",
    "HFO": "HFO_380_{hub}_USD",
    "MGO": "MGO_05S_{hub}_USD",
    "MDO": "MGO_05S_{hub}_USD",  # no MDO quote exists; MGO is the nearest, and is flagged as a proxy
    "LNG": "JKM_LNG_USD",        # Asian LNG benchmark, $/mmbtu, not port-specific
    "Methanol": None,            # not published
}
PRICE_PROXY_NOTES = {
    "MDO": "No MDO price is published; the MGO price is used as a proxy (MDO usually trades a little below it).",
    "LNG": "Priced from the JKM LNG benchmark (Asia), not a bunkering port.",
}
MMBTU_PER_TONNE_LNG = 52.0

HUBS: Dict[str, str] = {
    "SGSIN": "Singapore", "NLRTM": "Rotterdam", "AEFUJ": "Fujairah", "HKHKG": "Hong Kong",
    "USHOU": "Houston", "GIGIB": "Gibraltar", "USLAX": "Los Angeles", "USNYC": "New York",
    "BRSSZ": "Santos",
}
DEFAULT_HUB = "SGSIN"
# Nearest quoted hub for each twin port.
PORT_HUB: Dict[str, str] = {
    "Singapore": "SGSIN", "Tanjung Pelepas": "SGSIN", "Tanjung Priok": "SGSIN", "Laem Chabang": "SGSIN",
    "Rotterdam": "NLRTM", "Antwerp": "NLRTM", "Hamburg": "NLRTM", "Felixstowe": "NLRTM",
    "Dubai (Jebel Ali)": "AEFUJ", "Mundra": "AEFUJ", "Nhava Sheva (Mumbai)": "AEFUJ",
    "Hong Kong": "HKHKG", "Shenzhen": "HKHKG", "Guangzhou": "HKHKG",
    "Los Angeles": "USLAX", "Long Beach": "USLAX", "New York": "USNYC",
}

# Approximate fuel burn at service speed, tonnes of HFO-equivalent per day.
SHIP_CLASSES: List[Dict] = [
    {"value": "Container Ship (Feeder, ~2,000 TEU)", "group": "Container", "t_per_day": 30, "knots": 16},
    {"value": "Container Ship (Panamax, ~5,000 TEU)", "group": "Container", "t_per_day": 80, "knots": 19},
    {"value": "Container Ship (Post-Panamax, ~9,000 TEU)", "group": "Container", "t_per_day": 120, "knots": 20},
    {"value": "Container Ship (Ultra-Large, ~20,000 TEU)", "group": "Container", "t_per_day": 190, "knots": 19},
    {"value": "Bulk Carrier (Handysize)", "group": "Bulk", "t_per_day": 22, "knots": 13},
    {"value": "Bulk Carrier (Panamax)", "group": "Bulk", "t_per_day": 30, "knots": 13.5},
    {"value": "Bulk Carrier (Capesize)", "group": "Bulk", "t_per_day": 45, "knots": 13.5},
    {"value": "Tanker (Product / MR)", "group": "Tanker", "t_per_day": 28, "knots": 13},
    {"value": "Tanker (Aframax)", "group": "Tanker", "t_per_day": 42, "knots": 13.5},
    {"value": "Tanker (Suezmax)", "group": "Tanker", "t_per_day": 55, "knots": 14},
    {"value": "Tanker (VLCC)", "group": "Tanker", "t_per_day": 70, "knots": 14.5},
    {"value": "LNG Carrier", "group": "Gas", "t_per_day": 100, "knots": 17},
    {"value": "Ro-Ro / Car Carrier", "group": "Other", "t_per_day": 50, "knots": 18},
    {"value": "General Cargo Ship", "group": "Other", "t_per_day": 16, "knots": 12},
    {"value": "Cruise Ship", "group": "Other", "t_per_day": 150, "knots": 19},
    {"value": "Tug / Offshore Support Vessel", "group": "Other", "t_per_day": 9, "knots": 10},
    # Small-craft classes from the Niger Delta dataset the trained model learned from.
    {"value": "Tanker Ship", "group": "Niger Delta dataset", "t_per_day": 4, "knots": 10},
    {"value": "Oil Service Boat", "group": "Niger Delta dataset", "t_per_day": 3, "knots": 10},
    {"value": "Fishing Trawler", "group": "Niger Delta dataset", "t_per_day": 1.5, "knots": 9},
    {"value": "Surfer Boat", "group": "Niger Delta dataset", "t_per_day": 0.6, "knots": 12},
]
SHIP_BY_NAME = {s["value"]: s for s in SHIP_CLASSES}

WEATHER_FACTORS = {"Calm": 1.0, "Moderate": 1.05, "Stormy": 1.15}

LEGACY_ROUTES = ["Warri-Bonny", "Port Harcourt-Lagos", "Bonny-Lagos", "Lagos-Warri"]
