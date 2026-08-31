from typing import Any, Dict, List, Optional, Sequence

# Fixed, ordered set of numeric features the ML risk model is trained and
# predicted on. Both training (pipeline/pipeline.py) and inference
# (RiskModel) must vectorize through this same list so column order never
# drifts between the two.
FEATURE_COLUMNS: List[str] = [
    "event_severity_score",
    "event_source_provided",
    "event_has_description",
    "route_status_score",
    "route_has_origin",
    "route_has_destination",
    "route_waypoint_count",
    "route_notes_provided",
    "risk_likelihood_score",
    "risk_impact_score",
    "risk_status_score",
    "risk_is_active",
    "risk_has_mitigation_plan",
]


class FeatureEngineer:
    @staticmethod
    def encode_severity(severity: Optional[str]) -> int:
        if not severity:
            return 1
        severity_map = {
            "critical": 4,
            "high": 3,
            "warning": 2,
            "medium": 2,
            "low": 1,
            "info": 1,
        }
        return severity_map.get(severity.strip().lower(), 1)

    @staticmethod
    def encode_status(status: Optional[str]) -> int:
        if not status:
            return 0
        status_map = {
            "pending": 1,
            "planned": 1,
            "in_progress": 2,
            "completed": 0,
            "failed": 3,
            "open": 2,
            "closed": 0,
        }
        return status_map.get(status.strip().lower(), 0)

    @staticmethod
    def encode_likelihood(likelihood: Optional[str]) -> int:
        if not likelihood:
            return 2
        likelihood_map = {
            "very high": 4,
            "high": 3,
            "medium": 2,
            "low": 1,
            "very low": 1,
        }
        return likelihood_map.get(likelihood.strip().lower(), 2)

    @staticmethod
    def encode_impact(impact: Optional[str]) -> int:
        if not impact:
            return 2
        impact_map = {
            "critical": 4,
            "high": 3,
            "medium": 2,
            "low": 1,
            "minor": 1,
        }
        return impact_map.get(impact.strip().lower(), 2)

    @classmethod
    def extract_event_features(cls, event: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "event_type": event.get("event_type"),
            "event_severity_score": cls.encode_severity(event.get("severity")),
            "event_source_provided": int(bool(event.get("source"))),
            "event_has_description": int(bool(event.get("description"))),
        }

    @classmethod
    def extract_route_features(cls, route: Dict[str, Any]) -> Dict[str, Any]:
        waypoints = route.get("waypoints")
        waypoint_count = 0
        if isinstance(waypoints, Sequence) and not isinstance(waypoints, str):
            waypoint_count = len(waypoints)
        elif isinstance(waypoints, str) and waypoints.strip():
            waypoint_count = waypoints.count(",") + 1
        return {
            "route_status_score": cls.encode_status(route.get("status")),
            "route_has_origin": int(bool(route.get("origin"))),
            "route_has_destination": int(bool(route.get("destination"))),
            "route_waypoint_count": waypoint_count,
            "route_notes_provided": int(bool(route.get("notes"))),
        }

    @classmethod
    def extract_risk_features(cls, risk: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "risk_type": risk.get("risk_type"),
            "risk_category": risk.get("category"),
            "risk_likelihood_score": cls.encode_likelihood(risk.get("likelihood")),
            "risk_impact_score": cls.encode_impact(risk.get("impact")),
            "risk_status_score": cls.encode_status(risk.get("status")),
            "risk_is_active": int(bool(risk.get("is_active"))),
            "risk_has_mitigation_plan": int(bool(risk.get("mitigation_plan"))),
        }

    @classmethod
    def combine_features(
        cls,
        event: Optional[Dict[str, Any]] = None,
        route: Optional[Dict[str, Any]] = None,
        risk: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        features: Dict[str, Any] = {}
        if event:
            features.update(cls.extract_event_features(event))
        if route:
            features.update(cls.extract_route_features(route))
        if risk:
            features.update(cls.extract_risk_features(risk))
        return features

    @staticmethod
    def to_vector(features: Dict[str, Any]) -> List[float]:
        """Project a feature dict onto FEATURE_COLUMNS, in order, filling
        anything missing (e.g. no risk record yet) with 0."""
        vector = []
        for name in FEATURE_COLUMNS:
            value = features.get(name, 0)
            if isinstance(value, bool):
                value = 1.0 if value else 0.0
            vector.append(float(value) if value is not None else 0.0)
        return vector
