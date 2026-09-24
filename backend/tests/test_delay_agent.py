"""Delay Intelligence Agent: lane statistics computed from real container
journeys, and how they are served.

The numbers here come from small synthetic journey files whose answers can
be checked by hand, so a wrong calculation can't hide behind "it looks
plausible on the real data". A few smoke tests then run against the real
data when it is present.
"""

from datetime import date, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.agents.delay import delay_agent as delay_module
from app.agents.delay.delay_agent import (
    JOURNEYS_PATH, MIN_LANE_JOURNEYS, DelayAgent, twin_port_name,
)
from app.api.dependencies.database import get_db
from app.api.routes import delay as delay_routes
from app.main import app
from app.models.governance import AgentIdentity, AgentHealth, AgentPermission

from tests.fleet_support import make_engine_and_session

client = TestClient(app)
with client:
    pass  # triggers lifespan startup once so governance agents exist


def write_journeys(path, lanes):
    """lanes: {(origin, destination): [(loaded 'YYYY-MM-DD', ocean_days), ...]}"""
    rows = []
    for (origin, destination), journeys in lanes.items():
        for loaded, days in journeys:
            loaded_on = pd.Timestamp(loaded)
            rows.append({"origin": origin, "destination": destination, "loaded_on": loaded_on,
                         "discharged_on": loaded_on + pd.Timedelta(days=days), "ocean_days": days})
    pd.DataFrame(rows).to_csv(path, index=False, date_format="%Y-%m-%d")
    return path


def spread(days, start="2021-03-01"):
    """One journey per day from `start`, cycling through `days`."""
    base = pd.Timestamp(start)
    return [((base + pd.Timedelta(days=i)).strftime("%Y-%m-%d"), d) for i, d in enumerate(days)]


# 15 journeys at 10 days and 5 at 30: median 10, p90 30, and 5/20 run 20 days past the median.
STEADY_THEN_LATE = [10] * 15 + [30] * 5


@pytest.fixture
def agent(tmp_path):
    journeys = write_journeys(tmp_path / "journeys.csv", {
        ("Shanghai", "Long Beach"): spread(STEADY_THEN_LATE),
        ("Vung Tau", "Houston"): spread([40] * 20),
        ("Ningbo", "Oakland"): spread([20] * 5),   # too few to report on
    })
    return DelayAgent(journeys_path=journeys, summary_path=tmp_path / "none.json", metrics_path=tmp_path / "none2.json")


# --- statistics ----------------------------------------------------------

def test_lane_statistics_are_computed_from_the_journeys(agent):
    result = agent.assess("Shanghai", "Long Beach")

    assert result["journeys"] == 20 and result["method"] == "lane_statistics"
    days = result["transit_days"]
    assert days["median"] == 10.0 and days["min"] == 10 and days["max"] == 30
    # Linear-interpolated percentiles of fifteen 10s and five 30s: p75 sits a quarter of
    # the way from the last 10 to the first 30.
    assert days["p90"] == 30.0 and days["p75"] == 15.0 and days["p25"] == 10.0
    assert days["mean"] == 15.0


def test_delayed_share_is_measured_against_the_lanes_own_median(agent):
    delayed = agent.assess("Shanghai", "Long Beach")["delayed"]

    # 30 >= 10 + 7 and 30 >= 10 + 10: the same five journeys either way.
    assert delayed["7"] == {"journeys": 5, "share": 0.25}
    assert delayed["10"] == {"journeys": 5, "share": 0.25}


def test_a_perfectly_steady_lane_has_no_delayed_journeys(agent):
    result = agent.assess("Vung Tau", "Houston")
    assert result["transit_days"]["median"] == 40.0 and result["delayed"]["7"]["share"] == 0.0


def test_no_model_score_is_ever_reported(agent):
    result = agent.assess("Shanghai", "Long Beach")
    assert result["method"] == "lane_statistics"
    assert not any("probability" in key or "score" in key for key in result)


# --- lanes that cannot be reported on ------------------------------------

def test_a_lane_with_too_few_journeys_is_refused_not_guessed(agent):
    with pytest.raises(ValueError, match=str(MIN_LANE_JOURNEYS)):
        agent.assess("Ningbo", "Oakland")


def test_a_lane_with_no_journeys_is_refused(agent):
    with pytest.raises(ValueError, match="No recorded journeys"):
        agent.assess("Shanghai", "Rotterdam")


def test_overview_lists_only_lanes_with_enough_history(agent):
    overview = agent.overview()

    assert overview["journeys"] == 45 and overview["lanes_recorded"] == 3 and overview["lanes_usable"] == 2
    assert overview["origins"] == ["Shanghai", "Vung Tau"]
    assert overview["destinations_by_origin"]["Shanghai"] == [{"destination": "Long Beach", "journeys": 20, "median_days": 10.0}]
    assert "Ningbo" not in overview["destinations_by_origin"]


# --- time and season -----------------------------------------------------

def test_monthly_trend_leaves_out_months_with_only_a_few_journeys(tmp_path):
    days = [10] * 30 + [50, 50]            # March 2021: 31 journeys of 10 d; April 1-2: two long ones
    path = write_journeys(tmp_path / "j.csv", {("Shanghai", "Long Beach"): spread(days)})
    result = DelayAgent(journeys_path=path, summary_path=tmp_path / "s", metrics_path=tmp_path / "m").assess("Shanghai", "Long Beach")

    assert [m["month"] for m in result["monthly"]] == ["2021-03"]      # April had 2 journeys, below the floor
    assert result["monthly"][0]["journeys"] == 31


def test_same_season_needs_enough_journeys_in_that_calendar_month(tmp_path):
    journeys = spread([10] * 20, start="2021-03-01") + spread([30] * 6, start="2022-03-01")
    path = write_journeys(tmp_path / "j.csv", {("Shanghai", "Long Beach"): journeys})
    agent = DelayAgent(journeys_path=path, summary_path=tmp_path / "s", metrics_path=tmp_path / "m")

    march = agent.assess("Shanghai", "Long Beach", loading_date=date(2023, 3, 10))["same_season"]
    october = agent.assess("Shanghai", "Long Beach", loading_date=date(2023, 10, 10))["same_season"]

    assert march == {"calendar_month": 3, "journeys": 26, "median_days": 10.0}
    assert october is None
    assert agent.assess("Shanghai", "Long Beach")["same_season"] is None


# --- confidence ----------------------------------------------------------

@pytest.mark.parametrize("journeys,expected", [(15, 0.74), (25, 0.8), (50, 0.95), (400, 0.95)])
def test_confidence_reflects_how_much_history_backs_the_lane(tmp_path, journeys, expected):
    path = write_journeys(tmp_path / "j.csv", {("Shanghai", "Long Beach"): spread([12] * journeys)})
    agent = DelayAgent(journeys_path=path, summary_path=tmp_path / "s", metrics_path=tmp_path / "m")
    assert agent.assess("Shanghai", "Long Beach")["confidence"] == expected


# --- digital twin context ------------------------------------------------

def test_a_lane_the_twin_covers_gets_its_ideal_transit_and_current_risk(agent):
    result = agent.assess("Shanghai", "Long Beach", live_corridor_scores={})
    lane = result["context"]["lane"]

    assert lane["lane_id"] == "shanghai-longbeach" and lane["distance_nm"] > 5000
    assert lane["typical_extra_days"] == round(10.0 - lane["ideal_transit_days"], 1)
    assert lane["risk"] is not None and "assumption" in lane["ideal_basis"]
    assert result["context"]["origin_port"]["has_congestion_data"] is True


def test_live_risk_is_left_out_when_no_live_data_was_supplied(agent):
    lane = agent.assess("Shanghai", "Long Beach", live_corridor_scores=None)["context"]["lane"]
    assert lane["risk"] is None and lane["risk_reason"] is None


def test_a_lane_outside_the_twin_says_so_instead_of_inventing_context(agent):
    context = agent.assess("Vung Tau", "Houston")["context"]
    assert context["lane"] is None and context["origin_port"] is None and context["destination_port"] is None


def test_journey_port_names_map_to_the_twins_names():
    assert twin_port_name("Yantian") == "Shenzhen"
    assert twin_port_name("Jawaharlal Nehru") == "Nhava Sheva (Mumbai)"
    assert twin_port_name("Rotterdam") == "Rotterdam"
    assert twin_port_name("Vung Tau") is None


# --- the API -------------------------------------------------------------

@pytest.fixture
def api(agent, monkeypatch):
    """Routes wired to the synthetic agent and an isolated in-memory database."""
    Session = make_engine_and_session()
    db = Session()
    db.add(AgentIdentity(id="delay-agent", agent_name="Delay Intelligence Agent", agent_type="ANALYZER",
                         version="v2.0", risk_level="LOW", criticality="MEDIUM", confidence_threshold=0.7))
    db.add(AgentHealth(agent_id="delay-agent", status="HEALTHY"))
    db.add(AgentPermission(agent_id="delay-agent", resource="ASSESS", action="EXECUTE"))
    db.commit()

    def override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(delay_routes, "get_delay_agent", lambda: agent)
    yield db
    app.dependency_overrides.pop(get_db, None)
    db.close()


def test_the_overview_route_returns_the_real_coverage(api):
    body = client.get("/api/delay/overview").json()
    assert body["lanes_usable"] == 2 and body["min_lane_journeys"] == MIN_LANE_JOURNEYS


def test_assessing_a_lane_runs_through_governance_and_returns_the_statistics(api):
    response = client.post("/api/delay/assess", json={"origin": "Shanghai", "destination": "Long Beach",
                                                       "loading_date": "2022-03-15"})
    body = response.json()

    assert response.status_code == 200 and body["status"] == "COMPLETED"
    assert body["assessment"]["transit_days"]["median"] == 10.0
    assert body["assessment"]["loading_date"] == "2022-03-15"
    from app.models.governance import AgentExecutionTrace
    trace = api.query(AgentExecutionTrace).one()
    assert trace.agent_id == "delay-agent" and trace.approval_status == "NOT_REQUIRED"


def test_an_unsupported_lane_is_a_404_with_the_reason(api):
    thin = client.post("/api/delay/assess", json={"origin": "Ningbo", "destination": "Oakland"})
    missing = client.post("/api/delay/assess", json={"origin": "Shanghai", "destination": "Rotterdam"})

    assert thin.status_code == 404 and str(MIN_LANE_JOURNEYS) in thin.json()["detail"]
    assert missing.status_code == 404


def test_a_quarantined_agent_cannot_assess(api):
    api.query(AgentIdentity).filter(AgentIdentity.id == "delay-agent").one().status = "QUARANTINED"
    api.commit()

    body = client.post("/api/delay/assess", json={"origin": "Shanghai", "destination": "Long Beach"}).json()

    assert body["status"] == "FAILED" and "QUARANTINED" in body["error"]


def test_the_old_prediction_routes_are_gone():
    assert client.post("/api/delay/predict", json={}).status_code == 404
    assert client.get("/api/delay/plant/PLANT03/profile").status_code == 404


# --- against the real data, when it is present ---------------------------

real_data = pytest.mark.skipif(not JOURNEYS_PATH.exists(), reason="real journey data not built (pipeline/build_transit_journeys.py)")


@real_data
def test_the_real_journeys_cover_real_named_ports():
    overview = DelayAgent().overview()

    assert overview["journeys"] > 1000 and overview["lanes_usable"] >= 10
    assert {"Shanghai", "Ningbo"} <= set(overview["origins"])
    assert not any(port.startswith(("PORT", "PLANT")) for port in overview["origins"])


@real_data
def test_a_real_lane_gives_sensible_transit_times():
    result = DelayAgent().assess("Shanghai", "Long Beach", live_corridor_scores={})
    days = result["transit_days"]

    assert 10 <= days["median"] <= 40 and days["p10"] <= days["median"] <= days["p90"] <= days["max"]
    assert result["context"]["lane"]["lane_id"] == "shanghai-longbeach"


@real_data
def test_the_saved_backtest_matches_what_the_service_claims():
    """The service serves lane statistics only because no model beat them.
    If a retrain ever reverses that, this fails and the design must be revisited."""
    backtest = DelayAgent().overview()["backtest"]
    if backtest is None:
        pytest.skip("backtest not run (pipeline/backtest_transit_models.py)")
    assert backtest["kind"] == "backtest"
    assert backtest["served_method"] == "lane statistics" and backtest["model_beats_baseline"] is False
