"""Fleet Monitoring Agent: what it concludes about a ship from a position
and the sea state there, the alerts it raises and clears, and its
governed cycle. Uses a fake sea-state feed and an in-memory database --
no network."""

from datetime import datetime, timedelta

import pytest

from app.agents.fleet import fleet_monitor_agent as monitor_module
from app.agents.fleet.fleet_monitor_agent import (
    FleetMonitorAgent, corridor_containing, run_monitoring_cycle, sync_tracker,
)
from app.agents.fleet.tracker import FleetTracker
from app.agents.ingestion.live_conditions_client import LiveConditionsClient
from app.core.config import settings
from app.models.fleet import Vessel, VesselAlert
from app.models.governance import AgentExecutionTrace, AgentHealth, AgentIdentity, AgentPermission, ApprovalRequest
from app.twin.digital_twin import get_digital_twin

from tests.fleet_support import (
    IMO_A, IMO_B, MMSI_A, MMSI_B, make_engine_and_session, make_user, make_vessel,
    position_msg, static_msg,
)

GIBRALTAR = (36.0, -5.6)
MID_ATLANTIC = (0.0, -30.0)
SUEZ = (29.35, 32.60)
FELIXSTOWE = (51.96, 1.35)


class FakeConditions(LiveConditionsClient):
    """The real severity bands, with the network call replaced."""

    def __init__(self, wave=0.4, gusts=12.0, fail=False):
        super().__init__()
        self.wave, self.gusts, self.fail, self.calls = wave, gusts, fail, 0

    def fetch_conditions(self, lat, lon):
        self.calls += 1
        if self.fail:
            raise RuntimeError("feed down")
        return {"wave_height_m": self.wave, "wind_gusts_kmh": self.gusts}


@pytest.fixture(autouse=True)
def live_sea_state(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_LIVE_INGESTION", True)
    monkeypatch.setattr(monitor_module, "fetch_live_corridor_scores", lambda: {})


@pytest.fixture
def db():
    session = make_engine_and_session()()
    yield session
    session.close()


@pytest.fixture
def tracker():
    return FleetTracker("test-key")


@pytest.fixture
def edges():
    return [attrs for _, _, attrs in get_digital_twin().graph.edges(data=True)]


def agent_for(tracker, **conditions):
    return FleetMonitorAgent(tracker=tracker, conditions_client=FakeConditions(**conditions))


def vessel_on(db, tracker, **kwargs):
    owner = make_user(db, "olive")
    vessel = make_vessel(db, owner, **kwargs)
    tracker.set_mmsis([int(vessel.mmsi)])
    return vessel


def alert_kinds(db, vessel, open_only=True):
    db.expire_all()
    query = db.query(VesselAlert).filter(VesselAlert.vessel_id == vessel.id)
    if open_only:
        query = query.filter(VesselAlert.resolved_at.is_(None))
    return sorted(a.kind for a in query.all())


# --- placing a ship ------------------------------------------------------

def test_a_ship_never_heard_from_is_awaiting_signal_with_no_invented_data(db, tracker, edges):
    vessel = vessel_on(db, tracker)

    agent_for(tracker).assess(db, vessel, edges)

    assert vessel.status == "awaiting_signal" and "No AIS position" in vessel.status_detail
    assert vessel.last_latitude is None and vessel.risk_score is None and vessel.lane_id is None


def test_a_live_ship_is_placed_in_the_digital_twin(db, tracker, edges):
    vessel = vessel_on(db, tracker)
    tracker._handle_message(position_msg(MMSI_A, *GIBRALTAR, sog=14.0))

    result = agent_for(tracker).assess(db, vessel, edges)

    assert result["status"] == "tracking" and vessel.status == "tracking"
    assert (vessel.last_latitude, vessel.last_longitude) == GIBRALTAR
    assert vessel.lane_id is not None and vessel.lane_offset_nm < 5
    assert vessel.nearest_port and vessel.nearest_port_nm > 0
    assert vessel.corridor is None  # Gibraltar is not one of the 8 monitored corridors


def test_a_ship_in_a_monitored_corridor_is_tagged_with_it(db, tracker, edges):
    vessel = vessel_on(db, tracker)
    tracker._handle_message(position_msg(MMSI_A, *SUEZ))

    agent_for(tracker).assess(db, vessel, edges)

    assert vessel.corridor == "Suez Canal (Gulf of Suez)"
    assert corridor_containing(*MID_ATLANTIC) is None


def test_a_ship_far_from_every_lane_is_not_forced_onto_one(db, tracker, edges):
    vessel = vessel_on(db, tracker)
    tracker._handle_message(position_msg(MMSI_A, -60.0, -120.0))  # Southern Ocean

    agent_for(tracker).assess(db, vessel, edges)

    assert vessel.lane_id is None and vessel.lane_offset_nm is None and vessel.lane_risk is None


# --- sea-state risk ------------------------------------------------------

def test_calm_water_at_the_ships_position_is_low_risk(db, tracker, edges):
    vessel = vessel_on(db, tracker)
    tracker._handle_message(position_msg(MMSI_A, *GIBRALTAR))

    agent_for(tracker, wave=0.4, gusts=10.0).assess(db, vessel, edges)

    assert vessel.risk_level == "low" and vessel.wave_height_m == 0.4
    assert alert_kinds(db, vessel) == []


def test_a_storm_raises_an_elevated_risk_alert_and_calm_clears_it(db, tracker, edges):
    vessel = vessel_on(db, tracker)
    tracker._handle_message(position_msg(MMSI_A, *GIBRALTAR))

    agent_for(tracker, wave=7.0, gusts=95.0).assess(db, vessel, edges)
    assert vessel.risk_level in ("medium", "high") and vessel.wind_gusts_kmh == 95.0
    assert alert_kinds(db, vessel) == ["ELEVATED_RISK"]

    agent_for(tracker, wave=0.3, gusts=8.0).assess(db, vessel, edges)
    assert vessel.risk_level == "low"
    assert alert_kinds(db, vessel) == []
    assert alert_kinds(db, vessel, open_only=False) == ["ELEVATED_RISK"]  # kept as history, resolved


@pytest.mark.parametrize("wave,gusts,level", [
    (0.4, 10.0, "low"),      # calm
    (1.5, 25.0, "low"),      # slight sea
    (3.0, 45.0, "medium"),   # moderate swell, strong winds
    (4.5, 70.0, "high"),     # rough seas, gale
    (7.0, 95.0, "high"),     # severe storm
])
def test_the_risk_level_follows_the_sea_state_band_not_the_compressed_model_score(db, tracker, edges, wave, gusts, level):
    vessel = vessel_on(db, tracker)
    tracker._handle_message(position_msg(MMSI_A, *GIBRALTAR))

    agent_for(tracker, wave=wave, gusts=gusts).assess(db, vessel, edges)

    assert vessel.risk_level == level and isinstance(vessel.risk_score, int)


def test_a_feed_outage_leaves_risk_empty_rather_than_guessing(db, tracker, edges):
    vessel = vessel_on(db, tracker)
    tracker._handle_message(position_msg(MMSI_A, *GIBRALTAR))

    agent_for(tracker, fail=True).assess(db, vessel, edges)

    assert vessel.status == "tracking" and vessel.risk_score is None
    assert "unavailable" in vessel.risk_detail


def test_sea_state_is_fetched_once_per_area_not_once_per_ship(db, tracker, edges):
    owner = make_user(db, "olive")
    ships = [make_vessel(db, owner, "A", MMSI_A), make_vessel(db, owner, "B", MMSI_B)]
    tracker.set_mmsis([int(MMSI_A), int(MMSI_B)])
    tracker._handle_message(position_msg(MMSI_A, 36.00, -5.60))
    tracker._handle_message(position_msg(MMSI_B, 36.05, -5.55))  # same quarter-degree cell
    agent = agent_for(tracker)

    for ship in ships:
        agent.assess(db, ship, edges)

    assert agent.conditions.calls == 1


# --- alerts --------------------------------------------------------------

def test_a_ship_gone_quiet_is_flagged_once_not_every_cycle(db, tracker, edges):
    vessel = vessel_on(db, tracker, last_latitude=10.0, last_longitude=60.0, last_sog=12.0,
                       last_position_at=datetime.utcnow() - timedelta(hours=3))
    agent = agent_for(tracker)

    agent.assess(db, vessel, edges)
    agent.assess(db, vessel, edges)

    assert vessel.status == "no_signal"
    assert alert_kinds(db, vessel) == ["AIS_SILENT"]
    assert db.query(VesselAlert).count() == 1


def test_the_silent_alert_clears_when_the_ship_reports_again(db, tracker, edges):
    vessel = vessel_on(db, tracker, last_latitude=10.0, last_longitude=60.0,
                       last_position_at=datetime.utcnow() - timedelta(hours=3))
    agent = agent_for(tracker)
    agent.assess(db, vessel, edges)
    assert alert_kinds(db, vessel) == ["AIS_SILENT"]

    tracker._handle_message(position_msg(MMSI_A, 10.0, 60.5))
    agent.assess(db, vessel, edges)

    assert vessel.status == "tracking" and alert_kinds(db, vessel) == []


def test_stationary_under_way_far_from_port_is_flagged(db, tracker, edges):
    vessel = vessel_on(db, tracker)
    tracker._handle_message(position_msg(MMSI_A, *MID_ATLANTIC, sog=0.1, nav=0))

    agent_for(tracker).assess(db, vessel, edges)

    assert "STOPPED_AT_SEA" in alert_kinds(db, vessel)


def test_stationary_near_a_port_is_normal(db, tracker, edges):
    vessel = vessel_on(db, tracker)
    tracker._handle_message(position_msg(MMSI_A, *FELIXSTOWE, sog=0.1, nav=0))

    agent_for(tracker).assess(db, vessel, edges)

    assert "STOPPED_AT_SEA" not in alert_kinds(db, vessel)


def test_anchored_or_moored_ships_are_not_flagged_as_stopped(db, tracker, edges):
    vessel = vessel_on(db, tracker)
    tracker._handle_message(position_msg(MMSI_A, *MID_ATLANTIC, sog=0.0, nav=1))  # at anchor

    agent_for(tracker).assess(db, vessel, edges)

    assert "STOPPED_AT_SEA" not in alert_kinds(db, vessel)


@pytest.mark.parametrize("nav,kind,severity", [(2, "NOT_UNDER_COMMAND", "high"), (6, "AGROUND", "critical")])
def test_distress_navigation_statuses_raise_serious_alerts(db, tracker, edges, nav, kind, severity):
    vessel = vessel_on(db, tracker)
    tracker._handle_message(position_msg(MMSI_A, *GIBRALTAR, nav=nav))

    agent_for(tracker).assess(db, vessel, edges)

    db.expire_all()
    alert = db.query(VesselAlert).filter(VesselAlert.kind == kind).one()
    assert alert.severity == severity and alert.owner_id == vessel.owner_id


# --- identity ------------------------------------------------------------

def test_the_ships_own_broadcast_verifies_or_flags_the_registered_identity(db, tracker, edges):
    good = vessel_on(db, tracker, name="EVER GIVEN", imo=IMO_B)
    tracker._handle_message(static_msg(MMSI_A, "EVER GIVEN", IMO_B))
    agent_for(tracker).assess(db, good, edges)
    assert good.verification == "verified" and good.ais_name == "EVER GIVEN" and good.ais_ship_type == "Cargo"

    owner = make_user(db, "omar")
    bad = make_vessel(db, owner, "TYPO SHIP", MMSI_B, imo=IMO_A)
    tracker.set_mmsis([int(MMSI_A), int(MMSI_B)])
    tracker._handle_message(static_msg(MMSI_B, "COMPLETELY DIFFERENT", IMO_B))
    agent_for(tracker).assess(db, bad, edges)
    assert bad.verification == "mismatch" and "COMPLETELY DIFFERENT" in bad.verification_note


# --- the governed cycle --------------------------------------------------

def seed_agent(db, **overrides):
    db.add(AgentIdentity(id="fleet-monitor-agent", agent_name="Fleet Monitoring Agent", agent_type="MONITOR",
                         version="v1.0", risk_level="LOW", criticality="MEDIUM", confidence_threshold=0.5,
                         **overrides))
    db.add(AgentHealth(agent_id="fleet-monitor-agent", status="HEALTHY"))
    db.add(AgentPermission(agent_id="fleet-monitor-agent", resource="MONITOR", action="EXECUTE"))
    db.commit()


def test_a_cycle_assesses_every_monitored_vessel_and_is_traced(db, tracker):
    seed_agent(db)
    owner = make_user(db, "olive")
    make_vessel(db, owner, "A", MMSI_A)
    make_vessel(db, owner, "B", MMSI_B)
    make_vessel(db, owner, "PAUSED", "477123400", monitoring_enabled=False)
    tracker.set_mmsis([int(MMSI_A), int(MMSI_B)])
    tracker._handle_message(position_msg(MMSI_A, *GIBRALTAR))

    summary = run_monitoring_cycle(db, agent_for(tracker))

    assert summary["vessels"] == 2 and summary["tracking"] == 1 and summary["awaiting_signal"] == 1
    trace = db.query(AgentExecutionTrace).one()
    assert trace.agent_id == "fleet-monitor-agent" and trace.output_data["vessels"] == 2
    assert trace.approval_status == "NOT_REQUIRED" and db.query(ApprovalRequest).count() == 0


def test_an_idle_system_writes_no_empty_traces(db, tracker):
    seed_agent(db)
    assert run_monitoring_cycle(db, agent_for(tracker)) is None
    assert db.query(AgentExecutionTrace).count() == 0


def test_a_quarantined_agent_cannot_run(db, tracker):
    seed_agent(db, status="QUARANTINED")
    owner = make_user(db, "olive")
    make_vessel(db, owner, "A", MMSI_A)

    with pytest.raises(PermissionError):
        run_monitoring_cycle(db, agent_for(tracker))


def test_one_failing_vessel_does_not_stop_the_rest(db, tracker, monkeypatch):
    seed_agent(db)
    owner = make_user(db, "olive")
    make_vessel(db, owner, "A", MMSI_A)
    make_vessel(db, owner, "B", MMSI_B)
    tracker.set_mmsis([int(MMSI_A), int(MMSI_B)])
    agent = agent_for(tracker)
    original = agent.assess

    def flaky(db_, vessel, edges_):
        if vessel.mmsi == MMSI_A:
            raise RuntimeError("boom")
        return original(db_, vessel, edges_)

    monkeypatch.setattr(agent, "assess", flaky)

    summary = run_monitoring_cycle(db, agent)

    assert summary["vessels"] == 2 and summary["awaiting_signal"] == 1


def test_confidence_scales_with_how_much_of_the_fleet_is_actually_visible():
    assert FleetMonitorAgent.confidence({"vessels": 4, "tracking": 4}) == 0.95
    assert FleetMonitorAgent.confidence({"vessels": 4, "tracking": 0}) == 0.6
    assert FleetMonitorAgent.confidence({"vessels": 0}) == 0.95


def test_sync_tracker_watches_exactly_the_vessels_with_monitoring_on(db, tracker):
    owner = make_user(db, "olive")
    make_vessel(db, owner, "ON", MMSI_A)
    make_vessel(db, owner, "OFF", MMSI_B, monitoring_enabled=False)

    sync_tracker(db, tracker)

    assert tracker.watched() == {int(MMSI_A)}
