"""Live voyage ETA and delay: reading AIS destinations, working out what is
left to sail along the twin's lanes, and the on-time verdict. Uses the real
digital twin; the API tests run on an isolated in-memory database."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.agents.fleet.tracker import fleet_tracker
from app.api.dependencies.auth import get_current_active_superuser, get_current_active_user
from app.api.dependencies.database import get_db
from app.core.constants import UserRole
from app.fleet.voyage import (
    assess_voyage, recent_speed, remaining_distance, resolve_ais_eta, resolve_destination,
)
from app.main import app
from app.models.fleet import Vessel, VoyagePlan
from app.models.governance import AgentHealth, AgentIdentity, AgentPermission
from app.twin.coordinates import PORT_COORDINATES
from app.twin.digital_twin import get_digital_twin

from tests.fleet_support import (
    MMSI_A, MMSI_B, make_engine_and_session, make_user, make_vessel, position_msg, reset_tracker,
)

NOW = datetime(2026, 9, 25, 12, 0)
twin = get_digital_twin()


def snapshot(name):
    node = twin.graph.nodes[name]
    return {"has_congestion_data": node["has_congestion_data"],
            "congestion_percentile": node["congestion_percentile"], "as_of": node["metrics_as_of"]}


def near_rotterdam(sog=10.0, **overrides):
    """A ship about 30 nm from Rotterdam, reporting now."""
    lat, lon = PORT_COORDINATES["Rotterdam"]
    args = dict(
        position={"latitude": lat + 0.5, "longitude": lon, "sog_knots": sog, "reported_at": NOW},
        ais_destination="NLRTM", ais_eta=None, plan_destination=None, scheduled_arrival=None,
        trail=None, twin=twin, port_snapshot=snapshot, now=NOW,
    )
    args.update(overrides)
    return assess_voyage(**args)


# --- reading a crew-typed destination ------------------------------------

@pytest.mark.parametrize("text,port", [
    ("NLRTM", "Rotterdam"), ("NL RTM", "Rotterdam"), ("rotterdam", "Rotterdam"),
    ("PORT OF LOS ANGELES", "Los Angeles"), ("US LGB", "Long Beach"),
    ("CNSHA>USLAX", "Los Angeles"), ("SHANGHAI-LONG BEACH", "Long Beach"),
    ("SG SIN", "Singapore"), ("JNPT", "Nhava Sheva (Mumbai)"),
])
def test_destination_text_is_resolved_to_a_twin_port(text, port):
    assert resolve_destination(text) == port


@pytest.mark.parametrize("text", [None, "", "FOR ORDERS", "CHINA", "AT SEA", "XXXXX"])
def test_an_unreadable_destination_is_unresolved_not_guessed(text):
    assert resolve_destination(text) is None


def test_ais_eta_takes_the_year_nearest_now():
    december = resolve_ais_eta({"month": 12, "day": 30, "hour": 6, "minute": 0}, datetime(2026, 1, 2))
    assert december == datetime(2025, 12, 30, 6, 0)
    assert resolve_ais_eta({"month": 10, "day": 2, "hour": 0, "minute": 0}, NOW) == datetime(2026, 10, 2)
    assert resolve_ais_eta(None, NOW) is None
    assert resolve_ais_eta({"month": 2, "day": 30, "hour": 0, "minute": 0}, NOW) is None


def test_speed_is_the_median_of_recent_underway_reports():
    trail = [[0, 0, "t", s] for s in (0.1, 11.0, 12.0, 30.0, 13.0)]
    assert recent_speed(1.0, trail) == (12.5, "median of the last 4 reports")
    assert recent_speed(9.0, []) == (9.0, "latest report")
    assert recent_speed(0.4, []) == (None, "not making passage")


# --- distance ------------------------------------------------------------

def test_distance_follows_the_twins_lanes_when_the_ship_is_on_one():
    lat, lon = PORT_COORDINATES["Shanghai"]
    result = remaining_distance(lat + 0.2, lon, "Rotterdam", twin)
    assert result["basis"] == "twin_lanes" and result["lane_id"]
    assert result["nm"] >= result["great_circle_nm"]


def test_a_ship_far_from_every_lane_is_measured_by_great_circle_and_says_so():
    result = remaining_distance(-45.0, -110.0, "Los Angeles", twin)
    assert result["basis"] == "great_circle" and result["lane_id"] is None
    assert result["nm"] == result["great_circle_nm"]


# --- the verdict ---------------------------------------------------------

def test_on_time_early_and_late_are_judged_against_the_scheduled_arrival():
    predicted = near_rotterdam()
    assert predicted["status"] == "no_reference" and predicted["predicted_arrival"]

    due_in_a_week = near_rotterdam(scheduled_arrival=NOW + timedelta(days=7))
    due_long_ago = near_rotterdam(scheduled_arrival=NOW - timedelta(days=3))
    due_about_now = near_rotterdam(scheduled_arrival=datetime.fromisoformat(predicted["predicted_arrival"].rstrip("Z")))

    assert due_in_a_week["status"] == "early" and due_in_a_week["references"]["scheduled"]["delta_hours"] < 0
    assert due_long_ago["status"] == "late" and due_long_ago["references"]["scheduled"]["delta_hours"] > 24
    assert due_about_now["status"] == "on_time"


def test_the_ships_own_eta_is_the_reference_when_there_is_no_plan():
    eta = {"month": 9, "day": 20, "hour": 0, "minute": 0}
    result = near_rotterdam(ais_eta=eta)
    assert result["status"] == "late" and "broadcast" in result["headline"]
    assert "scheduled" not in result["references"]


def test_the_plan_beats_the_ships_broadcast_destination_and_flags_the_conflict():
    result = near_rotterdam(plan_destination="Antwerp", ais_destination="NLRTM")
    assert result["destination"]["port"] == "Antwerp" and result["destination"]["source"] == "plan"
    assert any("broadcasting Rotterdam" in flag for flag in result["flags"])


def test_missing_information_gives_a_status_not_a_guess():
    assert near_rotterdam(position=None)["status"] == "no_position"
    no_destination = near_rotterdam(ais_destination="FOR ORDERS")
    assert no_destination["status"] == "no_destination" and no_destination["predicted_arrival"] is None
    assert any("FOR ORDERS" in flag for flag in no_destination["flags"])
    anchored = near_rotterdam(sog=0.2)
    assert anchored["status"] == "not_underway" and anchored["predicted_arrival"] is None


def test_the_destination_ports_congestion_is_reported_from_its_own_history():
    result = near_rotterdam()
    assert result["port_signal"]["level"] in {"congested", "normal", "quiet"}
    assert "percentile" in result["port_signal"]["text"]


def test_a_port_without_congestion_data_gets_no_signal_rather_than_a_calm_one():
    lat, lon = PORT_COORDINATES["Mundra"]
    result = near_rotterdam(
        position={"latitude": lat + 0.3, "longitude": lon, "sog_knots": 10.0, "reported_at": NOW},
        ais_destination="INMUN",
    )
    assert result["port_signal"] is None and result["predicted_arrival"]


def test_an_old_position_is_flagged():
    lat, lon = PORT_COORDINATES["Rotterdam"]
    result = near_rotterdam(position={"latitude": lat + 0.5, "longitude": lon, "sog_knots": 10.0,
                                      "reported_at": NOW - timedelta(hours=3)})
    assert any("minutes old" in flag for flag in result["flags"])


# --- the API -------------------------------------------------------------

client = TestClient(app)
with client:
    pass


@pytest.fixture
def db():
    Session = make_engine_and_session()
    session = Session()
    session.add(AgentIdentity(id="delay-agent", agent_name="Delay Intelligence Agent", agent_type="ANALYZER",
                              version="v2.0", risk_level="LOW", criticality="MEDIUM", confidence_threshold=0.7))
    session.add(AgentHealth(agent_id="delay-agent", status="HEALTHY"))
    session.add(AgentPermission(agent_id="delay-agent", resource="ASSESS", action="EXECUTE"))
    session.commit()

    def override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    reset_tracker()
    yield session
    app.dependency_overrides.clear()
    reset_tracker()
    session.close()


def act_as(user):
    app.dependency_overrides.pop(get_current_active_superuser, None)
    app.dependency_overrides[get_current_active_user] = lambda: user


def track(vessel, lat, lon, sog=12.0):
    fleet_tracker.set_mmsis([int(vessel.mmsi)])
    fleet_tracker._handle_message(position_msg(vessel.mmsi, lat, lon, sog=sog))


def test_a_tracked_vessel_gets_an_eta_through_a_governed_run(db):
    owner = make_user(db, "owner")
    vessel = make_vessel(db, owner)
    act_as(owner)
    lat, lon = PORT_COORDINATES["Rotterdam"]
    track(vessel, lat + 0.5, lon)
    client.put(f"/api/delay/voyages/{vessel.id}", json={"destination_port": "Rotterdam"})

    body = client.get("/api/delay/voyages").json()
    voyage = body["voyages"][0]

    assert voyage["status"] == "no_reference" and voyage["predicted_arrival"]
    assert voyage["destination"] == {"port": "Rotterdam", "source": "plan", "ais_declared": None, "ais_resolved": None}
    assert voyage["is_mine"] is True and body["summary"] == {"no_reference": 1}
    from app.models.governance import AgentExecutionTrace
    assert db.query(AgentExecutionTrace).filter(AgentExecutionTrace.agent_id == "delay-agent").count() == 1


def test_a_plan_with_a_due_date_turns_the_eta_into_a_verdict(db):
    owner = make_user(db, "owner")
    vessel = make_vessel(db, owner)
    act_as(owner)
    lat, lon = PORT_COORDINATES["Rotterdam"]
    track(vessel, lat + 0.5, lon)
    due = (datetime.utcnow() - timedelta(days=4)).isoformat() + "Z"

    saved = client.put(f"/api/delay/voyages/{vessel.id}", json={"destination_port": "Rotterdam", "scheduled_arrival": due})
    voyage = client.get("/api/delay/voyages").json()["voyages"][0]

    assert saved.json()["plan"]["destination_port"] == "Rotterdam"
    assert voyage["status"] == "late" and voyage["plan"]["scheduled_arrival"]


def test_a_plan_can_only_name_a_twin_port_and_clearing_it_removes_it(db):
    owner = make_user(db, "owner")
    vessel = make_vessel(db, owner)
    act_as(owner)

    assert client.put(f"/api/delay/voyages/{vessel.id}", json={"destination_port": "Atlantis"}).status_code == 422
    client.put(f"/api/delay/voyages/{vessel.id}", json={"destination_port": "Antwerp"})
    assert db.query(VoyagePlan).count() == 1
    assert client.put(f"/api/delay/voyages/{vessel.id}", json={}).json() == {"plan": None}
    db.expire_all()
    assert db.query(VoyagePlan).count() == 0


def test_plans_follow_fleet_ownership_and_roles(db):
    owner, other = make_user(db, "owner"), make_user(db, "other")
    supervisor = make_user(db, "boss", UserRole.SUPERVISOR)
    vessel = make_vessel(db, owner)

    act_as(other)
    assert client.put(f"/api/delay/voyages/{vessel.id}", json={"destination_port": "Antwerp"}).status_code == 404
    assert client.get("/api/delay/voyages").json()["voyages"] == []
    assert client.get("/api/delay/voyages?scope=all").status_code == 403

    act_as(supervisor)
    assert client.get("/api/delay/voyages?scope=all").json()["voyages"][0]["owner"] == "owner"
    assert client.put(f"/api/delay/voyages/{vessel.id}", json={"destination_port": "Antwerp"}).status_code == 403


def test_removing_a_vessel_removes_its_plan(db):
    owner = make_user(db, "owner")
    vessel = make_vessel(db, owner)
    act_as(owner)
    client.put(f"/api/delay/voyages/{vessel.id}", json={"destination_port": "Antwerp"})

    assert client.delete(f"/api/fleet/vessels/{vessel.id}").status_code == 204
    db.expire_all()
    assert db.query(VoyagePlan).count() == 0 and db.query(Vessel).count() == 0


def test_a_vessel_not_yet_heard_from_says_so(db):
    owner = make_user(db, "owner")
    make_vessel(db, owner, mmsi=MMSI_B)
    act_as(owner)

    voyage = client.get("/api/delay/voyages").json()["voyages"][0]
    assert voyage["status"] == "no_position" and voyage["predicted_arrival"] is None
