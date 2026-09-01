"""Typed contracts for agent-to-agent hand-offs.

Distinct from the CRUD schemas elsewhere in this package (event.py,
risk.py, ...), which shape HTTP request/response bodies for persisted
records. These describe what one agent hands to the next inside a
workflow run -- ingestion's output is risk's input, risk's output feeds
routing, and so on.

Before this, those hand-offs were plain dicts read with .get(), so a
missing or renamed key failed silently instead of loudly. The clearest
example was the coordinator reading a risk score as
`risk.get("score", 50)` -- a broken risk agent produced a fabricated
"medium risk" instead of an error. A required field on one of these
models raises at construction time instead.

HTTP routes that call these agents directly (dashboard.py, risks.py)
still work with dicts for their own responses -- call `.model_dump()`
on the result where a dict is needed, right at that call site.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IngestedEvent(BaseModel):
    """Output of IngestionAgent.collect_data_with_confidence()."""

    event_type: str
    severity: str = "info"
    source: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    timestamp: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # Raw sea-state reading behind `severity`, when the live feed supplied one.
    conditions: Optional[Dict[str, Any]] = None
    weather: Optional[Dict[str, Any]] = None
    related_news: List[Dict[str, Any]] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    """Output of RiskAgent.calculate_risk()."""

    score: int = Field(..., ge=0, le=100)
    severity: str
    likelihood: str
    impact: str
    category: str
    description: Optional[str] = None
    scoring_method: str


class RouteRecommendation(BaseModel):
    """Output of RouteAgent.suggest_route().

    Placeholder shape matching today's rule-based ladder in
    agents/route/route_agent.py. Slice 06 replaces that ladder with a
    real multi-objective optimizer; this contract is what its output
    needs to satisfy when it does.
    """

    route: str
    reason: str
