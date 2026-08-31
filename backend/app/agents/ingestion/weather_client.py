from typing import Any, Dict, Optional

import requests


class WeatherClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openweathermap.org/data/2.5/weather",
        default_units: str = "metric",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.default_units = default_units

    def fetch_current_weather(
        self,
        location: str,
        units: Optional[str] = None,
    ) -> Dict[str, Any]:
        if units is None:
            units = self.default_units

        params = {
            "q": location,
            "units": units,
        }
        if self.api_key:
            params["appid"] = self.api_key

        response = requests.get(self.base_url, params=params)
        response.raise_for_status()

        payload = response.json()
        return self._serialize_weather(payload)

    def _serialize_weather(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "location": payload.get("name"),
            "coordinates": payload.get("coord"),
            "weather": payload.get("weather", []),
            "temperature": payload.get("main", {}).get("temp"),
            "feels_like": payload.get("main", {}).get("feels_like"),
            "pressure": payload.get("main", {}).get("pressure"),
            "humidity": payload.get("main", {}).get("humidity"),
            "wind": payload.get("wind"),
            "clouds": payload.get("clouds"),
            "timestamp": payload.get("dt"),
        }