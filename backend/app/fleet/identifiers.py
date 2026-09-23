"""Ship identity: IMO number, MMSI, name normalization and verification.

Ships are identified by two international conventions -- the IMO number
(a permanent 7-digit hull identifier with a check digit) and the MMSI
(the 9-digit radio identity AIS transmits, whose first three digits are a
Maritime Identification Digits country code). Validating both up front
catches typos before they would silently start tracking a different ship.

`verify_identity` cross-checks what the operator typed against what the
ship itself broadcasts over AIS, so a wrong MMSI shows up as a mismatch
instead of quietly monitoring someone else's vessel.
"""

import re
from typing import Optional, Tuple

VESSEL_TYPES = [
    "container_ship", "tanker", "bulk_carrier", "general_cargo",
    "ro_ro", "gas_carrier", "passenger", "other",
]

VESSEL_TYPE_LABELS = {
    "container_ship": "Container ship",
    "tanker": "Tanker",
    "bulk_carrier": "Bulk carrier",
    "general_cargo": "General cargo",
    "ro_ro": "Ro-Ro / vehicle carrier",
    "gas_carrier": "LNG / LPG carrier",
    "passenger": "Passenger / cruise",
    "other": "Other",
}

_MMSI_RE = re.compile(r"^[2-7]\d{8}$")
_IMO_PREFIX_RE = re.compile(r"^\s*IMO[\s:.-]*", re.IGNORECASE)


def normalize_name(name: str) -> str:
    """Ship names are registered in capitals with single spaces."""
    return " ".join((name or "").upper().split())


def clean_imo(value: Optional[str]) -> Optional[str]:
    """'IMO 9811000' / ' 9811000 ' -> '9811000'; blank -> None."""
    if value is None:
        return None
    cleaned = _IMO_PREFIX_RE.sub("", str(value)).strip().replace(" ", "")
    return cleaned or None


def imo_is_valid(imo: str) -> bool:
    """7 digits whose last digit is the check digit: the first six digits
    multiplied by 7,6,5,4,3,2, summed, last digit of that sum."""
    if not imo or not re.fullmatch(r"\d{7}", imo):
        return False
    total = sum(int(d) * w for d, w in zip(imo[:6], (7, 6, 5, 4, 3, 2)))
    return total % 10 == int(imo[6])


def mmsi_is_valid(mmsi: str) -> bool:
    """9 digits with a ship-station country code (MID 201-775). This rules
    out coast stations, SAR aircraft, AIS-SART / man-overboard devices and
    other non-ship identities, which would never be a registered vessel."""
    if not mmsi or not _MMSI_RE.fullmatch(mmsi):
        return False
    return 201 <= int(mmsi[:3]) <= 775


def _alnum(text: Optional[str]) -> str:
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


def verify_identity(
    *,
    name: str,
    imo: Optional[str],
    ais_name: Optional[str],
    ais_imo: Optional[str],
) -> Tuple[str, Optional[str]]:
    """Compare the registered identity with what the ship broadcasts.

    Returns (status, note): 'verified', 'mismatch', or 'unverified'.

    The IMO is the only hard identifier, and it is carried in the ship's
    slow static AIS message (roughly every 6 minutes) -- position reports
    carry just the name. So:
      * both IMOs known: they must agree;
      * an IMO was registered but the ship hasn't broadcast its own yet: a
        name that clearly differs is a mismatch, but a matching name is NOT
        enough to verify -- it stays unverified until the IMO confirms it;
      * no IMO registered: the name is all there is to compare.
    AIS reports 0 for an unknown IMO, which counts as absent.
    """
    ais_imo = str(ais_imo) if ais_imo and str(ais_imo) not in ("0", "0000000") else None
    ais_name = ais_name.strip() if ais_name else None
    names_agree = bool(ais_name) and _alnum(name) == _alnum(ais_name)

    if imo and ais_imo:
        if str(imo) == ais_imo:
            return "verified", None
        detail = f" ({ais_name})" if ais_name else ""
        return "mismatch", f"This MMSI broadcasts IMO {ais_imo}{detail}, not {imo}."

    if imo:  # registered IMO, ship's own IMO not heard yet
        if ais_name and not names_agree:
            return "mismatch", f"This MMSI broadcasts the name {ais_name}, not {normalize_name(name)}."
        if names_agree:
            return "unverified", "The name matches; waiting for the ship to broadcast its IMO number to confirm."
        return "unverified", None

    if ais_name:  # nothing registered but a name
        if names_agree:
            return "verified", None
        return "mismatch", f"This MMSI broadcasts the name {ais_name}, not {normalize_name(name)}."

    return "unverified", None
