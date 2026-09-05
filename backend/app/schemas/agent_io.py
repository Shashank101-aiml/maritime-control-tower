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


class Decision(BaseModel):
    """Output of DecisionAgent.decide() -- spec Slice 07/section 13's
    structured recommendation: a real trade-off comparison, not just
    the route on its own.

    `baseline` is the shortest-distance candidate among the
    RouteRecommendation's own ranked set (what a naive "just minimize
    distance" chooser would pick) -- not an invented "current voyage",
    since this pipeline has never had one. `recommended` is the actual
    risk-weighted top pick. Every delta below is real arithmetic
    between two candidates RouteOptimizer already scored; when they're
    the same candidate every delta is honestly zero rather than a
    forced trade-off narrative.
    """

    recommendation: str
    baseline_lane_ids: List[str]
    recommended_lane_ids: List[str]
    expected_delay_days: float
    estimated_cost_change_usd: float
    risk_reduction: int
    confidence: float = Field(..., ge=0, le=1)
    requires_human_approval: bool


class ScenarioResult(BaseModel):
    """Output of SimulationAgent.simulate() -- spec Slice 08/section 11:
    what the real optimizer would recommend for the same origin/
    destination if a chosen monitored corridor's conditions worsen
    (MODERATE) or the corridor becomes fully impassable (SEVERE),
    compared against today's real baseline recommendation.

    The simulated graph is a copy of the live digital twin with only
    the chosen corridor's crossing lanes modified -- every other lane's
    real distance/cost/congestion is untouched, and the same
    RouteOptimizer that produces real recommendations elsewhere scores
    the result. `scenario_*` fields are null when no route survives the
    scenario (SEVERE can genuinely disconnect a port pair) rather than
    a fabricated fallback path.
    """

    scenario: str
    corridor: str
    origin: str
    destination: str
    baseline_lane_ids: List[str]
    baseline_risk: int
    baseline_distance_nm: float
    scenario_lane_ids: Optional[List[str]] = None
    scenario_risk: Optional[int] = None
    scenario_distance_nm: Optional[float] = None
    lanes_affected: int
    route_changed: bool
    no_viable_route: bool
    summary: str


class NewsUnderstanding(BaseModel):
    """Output of EventUnderstandingAgent.analyze() -- spec section 7:
    structured extraction over free text (a news article's title +
    description + content), not "hand the whole article to an LLM" for
    what's fundamentally text classification + entity matching. See
    event_understanding_agent.py for exactly how category and location
    matching are computed -- both are transparent, reproducible
    techniques (TF-IDF cosine similarity against hand-written reference
    terms; substring matching against this system's own real port/
    corridor names), not a black-box model reporting invented metrics.
    """

    category: str
    category_confidence: float = Field(..., ge=0, le=1)
    matched_locations: List[str]
    reasoning: str


class AnomalyReport(BaseModel):
    """Output of AnomalyAgent.detect() -- spec section 8. Unsupervised
    (Isolation Forest, pipeline/train_anomaly_model.py) over the same
    real per-port weekly congestion columns the digital twin and
    congestion classifier already use -- there is no labeled "anomaly"
    ground truth in this data to train a supervised model against, and
    inventing one would defeat the point.
    """

    anomaly_detected: bool
    anomaly_score: float
    affected_region: str
    reason: str
