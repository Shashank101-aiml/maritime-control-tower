"""Live bunker prices from oilpriceapi.com. Cached, so one page view costs
at most a handful of calls per half hour; a failure leaves the price out
(the estimate then says it has no price) rather than falling back to an
invented one."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any, Dict, Optional

import requests

from app.core.config import settings
from app.core.logging import get_logger
from app.fuel.reference import (
    DEFAULT_HUB, FUELS, MMBTU_PER_TONNE_LNG, PRICE_CODES, PRICE_PROXY_NOTES,
)

logger = get_logger(__name__)

URL = "https://api.oilpriceapi.com/v1/prices/latest"
TTL_SECONDS = 30 * 60
FAILURE_TTL_SECONDS = 60


class PriceClient:
    def __init__(self) -> None:
        self._cache: Dict[str, Any] = {}
        self._lock = Lock()

    @property
    def configured(self) -> bool:
        return bool(settings.OIL_PRICE_API)

    def _fetch(self, code: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            hit = self._cache.get(code)
            if hit and hit[0] > time.time():
                return hit[1]
        result = None
        try:
            response = requests.get(
                URL, params={"by_code": code}, timeout=8,
                headers={"Authorization": f"Token {settings.OIL_PRICE_API}"},
            )
            if response.ok:
                data = response.json().get("data") or {}
                if data.get("price") is not None:
                    result = {"price": float(data["price"]), "as_of": data.get("updated_at") or data.get("created_at")}
            else:
                logger.warning("Oil price API returned %s for %s", response.status_code, code)
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Oil price API request for %s failed: %s", code, type(exc).__name__)
        with self._lock:
            self._cache[code] = (time.time() + (TTL_SECONDS if result else FAILURE_TTL_SECONDS), result)
        return result

    def bunker_price(self, fuel: str, hub: str) -> Dict[str, Any]:
        """USD per tonne of `fuel` at `hub`, with where it came from; usd_per_tonne is None if unavailable."""
        out: Dict[str, Any] = {"fuel": fuel, "hub": hub, "usd_per_tonne": None, "code": None, "as_of": None, "note": None}
        template = PRICE_CODES.get(fuel)
        if template is None:
            out["note"] = f"No {FUELS[fuel]['label']} price is published by the price service, so cost is not estimated."
            return out
        if not self.configured:
            out["note"] = "No OIL_PRICE_API key is set, so cost is not estimated."
            return out

        code = template.format(hub=hub)
        found = self._fetch(code)
        if found is None and hub != DEFAULT_HUB and "{hub}" in template:
            code = template.format(hub=DEFAULT_HUB)
            found = self._fetch(code)
            if found:
                out["note"] = f"No {fuel} quote for this hub; the Singapore price is used."
                out["hub"] = DEFAULT_HUB
        if found is None:
            out["note"] = "The price service didn't return a price, so cost is not estimated."
            return out

        price = found["price"] * MMBTU_PER_TONNE_LNG if fuel == "LNG" else found["price"]
        out.update(usd_per_tonne=round(price, 2), code=code, as_of=found["as_of"])
        proxy = PRICE_PROXY_NOTES.get(fuel)
        if proxy:
            out["note"] = proxy
        return out

    def all_prices(self, hub: str) -> Dict[str, Dict[str, Any]]:
        with ThreadPoolExecutor(max_workers=6) as pool:
            return dict(zip(FUELS, pool.map(lambda f: self.bunker_price(f, hub), FUELS)))


price_client = PriceClient()
