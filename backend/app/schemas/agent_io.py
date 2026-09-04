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


class RouteAlternative(BaseModel):
    """One scored candidate path through the digital twin between two
    ports -- a real sequence of lanes, not a label. `score` is the
    weighted composite (lower is better) computed by RouteOptimizer,
    normalized against the other candidates considered for the same
    query, so it's only comparable within one RouteRecommendation."""

    lane_ids: List[str]
    distance_nm: float
    transit_days: float
    cost_usd: float
    emissions_estimate: float
    risk: int = Field(..., ge=0, le=100)
    score: float


class RouteRecommendation(BaseModel):
    """Output of RouteAgent.suggest_route().

    Real multi-objective optimization over the digital twin
    (app/twin/digital_twin.py) as of Slice 06 -- `route`/`reason` stay
    as a human-readable summary of the top-ranked candidate so existing
    consumers (recommendation.py, the frontend) don't break on the
    shape change, but every other field here is real: an actual
    sequence of shipping lanes with real distance/cost/risk, not a
    label picked off a fixed ladder.

    Ranking only -- no current-vs-recommended delta framing. That's the
    Decision Agent's job (spec Slice 07), which consumes this ranked
    list to build the comparison.
    """

    route: str
    reason: str
    origin: str
    destination: str
    lane_ids: List[str]
    distance_nm: float
    transit_days: float
    cost_usd: float
    emissions_estimate: float
    risk: int = Field(..., ge=0, le=100)
    score: float
    alternatives: List[RouteAlternative] = Field(default_factory=list)
