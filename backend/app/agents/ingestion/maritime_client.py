import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class MaritimeClient:
    """Simple maritime data ingestion client for local sample data."""

    DEFAULT_SOURCE = (
        Path(__file__).resolve().parents[4] / "data" / "raw" / "example.json"
    )

    def __init__(self, source_path: Optional[Path] = None):
        self.source_path = source_path or self.DEFAULT_SOURCE

    def fetch_data(self) -> Dict[str, Any]:
        """Load raw maritime data from the configured source file."""
        if not self.source_path.exists():
            raise FileNotFoundError(
                f"Maritime source data not found: {self.source_path}"
            )

        with self.source_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def parse_event(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize raw maritime readings into an ingestion event."""
        event_type = raw_data.get("storm") or raw_data.get("event_type") or "Storm"
        location = raw_data.get("location") or raw_data.get("area") or "Arabian Sea"
        speed = raw_data.get("speed")

        return {
            "event_type": str(event_type).title(),
            "location": location,
            "severity": self._severity_from_speed(speed),
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "speed": speed,
                "raw_data": raw_data,
            },
        }

    def _severity_from_speed(self, speed: Any) -> str:
        """Convert a numeric speed reading into a severity band."""
        try:
            value = float(speed)
        except (TypeError, ValueError):
            return "MEDIUM"

        if value >= 80:
            return "HIGH"
        if value >= 50:
            return "MEDIUM"
        return "LOW"

    def get_event(self) -> Dict[str, Any]:
        """Fetch the raw maritime sample and return a normalized ingestion event."""
        raw_data = self.fetch_data()
        return self.parse_event(raw_data)
