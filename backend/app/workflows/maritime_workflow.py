from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.recommendation import Recommendation
from app.models.route import Route
from app.models.risk import Risk
from app.schemas.event import EventCreate
from app.schemas.risk import RiskCreate
from app.schemas.route import RouteCreate, RouteUpdate
from app.services.event_service import create_event
from app.services.notification_service import notify_event_alert
from app.services.risk_service import create_risk
from app.services.route_service import create_route, delete_route, get_route, update_route


class MaritimeWorkflow:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record_event(self, event_in: EventCreate) -> Any:
        event = create_event(self.db, event_in)

        if self._should_send_alert(event_in.severity):
            notify_event_alert(
                event_type=event_in.event_type,
                severity=event_in.severity,
                source=event_in.source,
                description=event_in.description,
            )
            self.assess_event_risk(event)

        return event

    def assess_event_risk(self, event: Any) -> Risk:
        severity = (event.severity or "").lower()
        likelihood = "high" if severity in {"critical", "error"} else "medium"
        impact = "high" if severity in {"critical", "error", "warning"} else "medium"

        risk_in = RiskCreate(
            risk_type="operational",
            category=event.event_type,
            description=(
                f"Event '{event.event_type}' reported from "
                f"{event.source or 'unknown source'}: {event.description or 'no description'}"
            ),
            likelihood=likelihood,
            impact=impact,
            estimated_cost=0.0,
            mitigation_plan="Review the event details, verify vessel status, and update operational controls.",
            status="open",
            is_active=True,
        )

        return create_risk(self.db, risk_in)

    def create_route_plan(self, route_in: RouteCreate) -> Route:
        return create_route(self.db, route_in)

    def update_route_plan(self, route_id: int, route_in: RouteUpdate) -> Route:
        route = get_route(self.db, route_id)
        if route is None:
            raise ValueError(f"Route with id={route_id} not found")
        return update_route(self.db, route, route_in)

    def delete_route_plan(self, route_id: int) -> Route:
        route = get_route(self.db, route_id)
        if route is None:
            raise ValueError(f"Route with id={route_id} not found")
        return delete_route(self.db, route)

    def assess_route_risk(self, route: Route) -> Risk:
        origin = getattr(route, "origin", "unknown origin")
        destination = getattr(route, "destination", "unknown destination")
        status = getattr(route, "status", "planned")

        risk_in = RiskCreate(
            risk_type="navigation",
            category="route",
            description=(
                f"Route from {origin} to {destination} with current status '{status}' "
                "should be reviewed for operational hazards and environmental conditions."
            ),
            likelihood="medium",
            impact="medium",
            estimated_cost=0.0,
            mitigation_plan="Validate route waypoints, check weather, and confirm communications before departure.",
            status="open",
            is_active=True,
        )

        return create_risk(self.db, risk_in)

    def create_recommendation_for_risk(self, risk: Risk) -> Recommendation:
        summary = f"Mitigation recommendation for {risk.risk_type} risk"
        recommendation = Recommendation(
            recommendation_type="safety",
            summary=summary,
            details=risk.mitigation_plan or "Define a mitigation plan and assign follow-up actions.",
            priority=1,
            status="pending",
            source=f"risk:{risk.id}",
            is_implemented=False,
        )

        self.db.add(recommendation)
        self.db.commit()
        self.db.refresh(recommendation)
        return recommendation

    def _should_send_alert(self, severity: Optional[str]) -> bool:
        if severity is None:
            return False
        return severity.lower() in {"warning", "error", "critical", "high"}
