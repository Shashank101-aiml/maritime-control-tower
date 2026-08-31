from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union


class Parser:
    def parse(self, payload: Any) -> Dict[str, Any]:
        if payload is None:
            return {}

        if isinstance(payload, str):
            return self.parse_text(payload)

        if isinstance(payload, dict):
            return self.parse_dict(payload)

        if isinstance(payload, list):
            return self.parse_list(payload)

        return {"raw_payload": str(payload)}

    def parse_dict(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if "event_type" in payload or "severity" in payload:
            return self.parse_event_payload(payload)
        if "origin" in payload or "destination" in payload:
            return self.parse_route_payload(payload)
        if "risk_type" in payload or "likelihood" in payload:
            return self.parse_risk_payload(payload)
        return {"payload": payload}

    def parse_list(self, payload: List[Any]) -> Dict[str, Any]:
        if not payload:
            return {}
        first = payload[0]
        if isinstance(first, dict):
            return self.parse_dict(first)
        return {"items": payload}

    def parse_text(self, text: str) -> Dict[str, Any]:
        text = text.strip()
        if not text:
            return {}

        try:
            parsed = json.loads(text)
            return self.parse(parsed)
        except json.JSONDecodeError:
            pass

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        data: Dict[str, Any] = {}
        for line in lines:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            data[key.strip().lower().replace(" ", "_")] = value.strip()

        return self.parse_dict(data) if data else {"text": text}

    def parse_event_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "event_type": self._to_str(payload.get("event_type") or payload.get("type")),
            "severity": self._to_str(payload.get("severity")),
            "source": self._to_str(
                payload.get("source")
                or payload.get("source_system")
                or payload.get("location")
            ),
            "description": self._to_str(payload.get("description")),
            "timestamp": self._normalize_timestamp(payload.get("timestamp")),
            "metadata": payload.get("metadata"),
        }

    def parse_route_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "origin": self._to_str(payload.get("origin")),
            "destination": self._to_str(payload.get("destination")),
            "status": self._to_str(payload.get("status")),
            "waypoints": payload.get("waypoints"),
            "estimated_time_of_arrival": self._normalize_timestamp(
                payload.get("estimated_time_of_arrival")
            ),
            "notes": self._to_str(payload.get("notes")),
        }

    def parse_risk_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "risk_type": self._to_str(payload.get("risk_type")),
            "category": self._to_str(payload.get("category")),
            "description": self._to_str(payload.get("description")),
            "likelihood": self._to_str(payload.get("likelihood")),
            "impact": self._to_str(payload.get("impact")),
            "estimated_cost": self._to_float(payload.get("estimated_cost")),
            "mitigation_plan": self._to_str(payload.get("mitigation_plan")),
            "status": self._to_str(payload.get("status")),
            "is_active": self._to_bool(payload.get("is_active")),
        }

    def _normalize_timestamp(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value).isoformat()
            except ValueError:
                return value
        return str(value)

    def _to_str(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value).strip()

    def _to_float(self, value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _to_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        value_str = str(value).strip().lower()
        return value_str in {"true", "1", "yes", "y", "on"}
