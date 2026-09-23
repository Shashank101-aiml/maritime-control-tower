"""Identity validation, twin geometry and the AIS fleet tracker's message
handling -- all pure logic, no network or database."""

import pytest

from app.agents.fleet.tracker import FleetTracker
from app.fleet.geometry import distance_to_segment_nm, nearest_lane, nearest_port
from app.fleet.identifiers import (
    clean_imo, imo_is_valid, mmsi_is_valid, normalize_name, verify_identity,
)
from app.twin.digital_twin import get_digital_twin

from tests.fleet_support import IMO_A, IMO_B, MMSI_A, MMSI_B, position_msg, static_msg


# --- IMO / MMSI ----------------------------------------------------------

@pytest.mark.parametrize("imo", [IMO_A, IMO_B, "9321483"])
def test_real_imo_numbers_pass_the_check_digit(imo):
    assert imo_is_valid(imo)


@pytest.mark.parametrize("imo", ["9074728", "9811001", "123", "12345678", "ABCDEFG", "", None])
def test_bad_imo_numbers_are_rejected(imo):
    assert not imo_is_valid(imo)


@pytest.mark.parametrize("raw,expected", [
    ("IMO 9811000", "9811000"), ("imo: 9811000", "9811000"), (" 9811000 ", "9811000"),
    ("IMO9811000", "9811000"), ("", None), ("   ", None), (None, None),
])
def test_clean_imo(raw, expected):
    assert clean_imo(raw) == expected


@pytest.mark.parametrize("mmsi", [MMSI_A, MMSI_B, "477123400", "201000000", "775999999"])
def test_ship_station_mmsis_are_accepted(mmsi):
    assert mmsi_is_valid(mmsi)


@pytest.mark.parametrize("mmsi", [
    "12345678",      # 8 digits
    "1234567890",    # 10 digits
    "970123456",     # AIS-SART
    "972123456",     # man-overboard device
    "111222333",     # first digit 1 = SAR aircraft
    "200123456",     # MID below 201
    "776000000",     # MID above 775
    "00123456X", "", None,
])
def test_non_ship_or_malformed_mmsis_are_rejected(mmsi):
    assert not mmsi_is_valid(mmsi)


def test_names_are_normalized_the_way_they_are_registered():
    assert normalize_name("  ever   given ") == "EVER GIVEN"


# --- verification --------------------------------------------------------

def test_matching_imo_verifies():
    assert verify_identity(name="X", imo=IMO_B, ais_name="Y", ais_imo=IMO_B) == ("verified", None)


def test_a_different_imo_is_a_mismatch_that_names_both():
    status, note = verify_identity(name="EVER GIVEN", imo=IMO_B, ais_name="OTHER SHIP", ais_imo=IMO_A)
    assert status == "mismatch" and IMO_A in note and IMO_B in note and "OTHER SHIP" in note


def test_name_is_compared_ignoring_case_and_punctuation_when_imo_is_missing():
    assert verify_identity(name="Ever Given", imo=None, ais_name="EVER-GIVEN", ais_imo=None)[0] == "verified"
    assert verify_identity(name="Ever Given", imo=None, ais_name="MAERSK ALTA", ais_imo=None)[0] == "mismatch"


def test_a_matching_name_alone_does_not_verify_a_registered_imo():
    """Position reports carry the ship's name but not its IMO. A wrong IMO
    with the right name must not read as verified."""
    status, note = verify_identity(name="XIN TIAN JIN", imo=IMO_A, ais_name="XIN TIAN JIN", ais_imo=None)
    assert status == "unverified" and "waiting" in note


def test_a_clearly_different_name_is_a_mismatch_even_before_the_imo_arrives():
    status, note = verify_identity(name="EVER GIVEN", imo=IMO_B, ais_name="MAERSK ALTA", ais_imo=None)
    assert status == "mismatch" and "MAERSK ALTA" in note


def test_the_ships_own_imo_settles_it_either_way_once_heard():
    assert verify_identity(name="XIN TIAN JIN", imo=IMO_A, ais_name="XIN TIAN JIN", ais_imo=IMO_A)[0] == "verified"
    assert verify_identity(name="XIN TIAN JIN", imo=IMO_A, ais_name="XIN TIAN JIN", ais_imo=IMO_B)[0] == "mismatch"


def test_nothing_broadcast_yet_means_unverified_not_mismatch():
    assert verify_identity(name="X", imo=IMO_A, ais_name=None, ais_imo=None) == ("unverified", None)


def test_an_unknown_ais_imo_of_zero_counts_as_not_broadcast():
    # AIS sends 0 when the IMO is unknown: with no IMO registered the name decides...
    assert verify_identity(name="EVER GIVEN", imo=None, ais_name="EVER GIVEN", ais_imo="0")[0] == "verified"
    # ...but a registered IMO stays unconfirmed rather than being called a mismatch.
    assert verify_identity(name="EVER GIVEN", imo=IMO_B, ais_name="EVER GIVEN", ais_imo="0")[0] == "unverified"


# --- geometry ------------------------------------------------------------

def test_distance_to_a_segment_is_perpendicular_when_inside_and_endpoint_when_beyond():
    a, b = (0.0, 0.0), (0.0, 1.0)  # one degree of longitude along the equator = 60 nm
    assert distance_to_segment_nm(1.0, 0.5, a, b) == pytest.approx(60.0, abs=0.5)
    assert distance_to_segment_nm(0.0, 2.0, a, b) == pytest.approx(60.0, abs=0.5)


def test_a_ship_at_gibraltar_is_on_a_suez_europe_lane():
    edges = [attrs for _, _, attrs in get_digital_twin().graph.edges(data=True)]
    edge, offset = nearest_lane(36.0, -5.6, edges)
    assert offset < 5
    assert "Strait of Gibraltar" in edge["waypoints"]


def test_lane_matching_works_across_the_antimeridian():
    """Trans-Pacific lanes cross +/-180; a ship just west of the line must
    still be matched to one rather than to a lane on the far side of the world."""
    edges = [attrs for _, _, attrs in get_digital_twin().graph.edges(data=True)]
    edge, offset = nearest_lane(33.0, 179.5, edges)
    assert offset < 120
    assert edge["lane_id"].split("-")[0] in {"shanghai", "ningbo", "busan", "shenzhen", "hongkong"}


def test_nearest_port():
    name, distance = nearest_port(51.9, 4.1)
    assert name == "Rotterdam" and distance < 20


# --- the AIS fleet tracker -----------------------------------------------

@pytest.fixture
def tracker():
    return FleetTracker("test-key")


def test_subscription_is_global_but_filtered_to_the_watched_mmsis(tracker):
    tracker.set_mmsis([int(MMSI_B), int(MMSI_A)])
    sub = tracker._subscription()
    assert sub["BoundingBoxes"] == [[[-90.0, -180.0], [90.0, 180.0]]]
    assert sub["FiltersShipMMSI"] == sorted([MMSI_A, MMSI_B])


def test_tracker_stays_disconnected_until_something_is_watched(tracker):
    assert tracker._should_connect() is False
    tracker.set_mmsis([int(MMSI_A)])
    assert tracker._should_connect() is True


def test_resubscribes_only_when_the_watched_set_actually_changes(tracker):
    tracker.set_mmsis([int(MMSI_A)])
    tracker._resubscribe.clear()
    tracker.set_mmsis([int(MMSI_A)])
    assert not tracker._resubscribe.is_set()
    tracker.set_mmsis([int(MMSI_A), int(MMSI_B)])
    assert tracker._resubscribe.is_set()


def test_a_watched_vessels_position_is_recorded_with_a_trail(tracker):
    tracker.set_mmsis([int(MMSI_A)])
    tracker._handle_message(position_msg(MMSI_A, 36.0, -5.6, sog=14.2, cog=88.0))
    tracker._handle_message(position_msg(MMSI_A, 36.1, -5.5))

    latest = tracker.latest(int(MMSI_A))
    assert (latest["latitude"], latest["longitude"]) == (36.1, -5.5)
    assert latest["received_at"] is not None
    assert [p[:2] for p in tracker.trail(int(MMSI_A))] == [[36.0, -5.6], [36.1, -5.5]]


def test_messages_for_unwatched_ships_are_ignored(tracker):
    tracker.set_mmsis([int(MMSI_A)])
    tracker._handle_message(position_msg(MMSI_B, 10.0, 10.0))
    assert tracker.latest(int(MMSI_B)) is None


def test_ais_not_available_positions_are_dropped(tracker):
    tracker.set_mmsis([int(MMSI_A)])
    tracker._handle_message(position_msg(MMSI_A, 91.0, 181.0))  # AIS's "not available"
    assert tracker.latest(int(MMSI_A)) is None


def test_static_data_is_kept_for_verification(tracker):
    tracker.set_mmsis([int(MMSI_A)])
    tracker._handle_message(static_msg(MMSI_A, "EVER GIVEN", IMO_B, ship_type=70))
    latest = tracker.latest(int(MMSI_A))
    assert latest["name"] == "EVER GIVEN" and latest["imo"] == int(IMO_B) and latest["ship_type"] == "Cargo"


def test_removing_a_vessel_clears_its_trail(tracker):
    tracker.set_mmsis([int(MMSI_A)])
    tracker._handle_message(position_msg(MMSI_A, 36.0, -5.6))
    tracker.set_mmsis([])
    assert tracker.trail(int(MMSI_A)) == []


def test_status_reports_capacity_and_configuration(tracker):
    tracker.set_mmsis([int(MMSI_A)])
    status = tracker.status()
    assert status["configured"] is True and status["tracked"] == 1 and status["capacity"] == 50
    assert FleetTracker(None).status()["configured"] is False
