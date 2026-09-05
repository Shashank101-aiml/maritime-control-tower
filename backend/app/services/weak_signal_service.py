"""Weak-signal / proactive layer (spec section 10): "disruption risk is
increasing at X" instead of a point-in-time score with no sense of
direction. A real least-squares linear trend over each corridor's own
recorded risk-score history (risk_history_by_corridor(), which already
re-scores real stored ConditionReading rows) -- not a forecast or a
trained model with no labeled "will this get worse" data to learn from.
r_squared is reported alongside the slope so a noisy, barely-linear
series is honestly distinguishable from a clean trend, not just given
the same "increasing"/"decreasing" label with silently different
reliability.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

# Below this many points there's nothing honest to say about a trend --
# two points is a line by definition, not evidence of one.
MIN_POINTS_FOR_TREND = 3

# A slope smaller than this (score points per hour) is noise, not a
# real trend -- chosen so a corridor would need to move roughly 5
# points over a full day to register as anything other than "stable".
STABLE_SLOPE_THRESHOLD = 0.2


def _to_naive_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    return datetime.fromisoformat(str(value).replace("Z", "")).replace(tzinfo=None)


def compute_trend(points: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    """points: [{"time": datetime|isoformat str, "score": number}, ...],
    any order -- sorted here by time before fitting. Returns a real
    least-squares slope (score points per hour) and r_squared for that
    fit, or an honest "insufficient_data" direction when there aren't
    enough points to say anything.
    """
    if len(points) < MIN_POINTS_FOR_TREND:
        return {
            "direction": "insufficient_data",
            "slope_per_hour": None,
            "r_squared": None,
            "n_points": len(points),
        }

    ordered = sorted(points, key=lambda p: _to_naive_datetime(p["time"]))
    t0 = _to_naive_datetime(ordered[0]["time"])
    xs = [(_to_naive_datetime(p["time"]) - t0).total_seconds() / 3600 for p in ordered]
    ys = [float(p["score"]) for p in ordered]

    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    ss_xx = sum((x - mean_x) ** 2 for x in xs)

    if ss_xx == 0:
        # every point at the same timestamp -- no time axis to fit against
        return {"direction": "insufficient_data", "slope_per_hour": None, "r_squared": None, "n_points": n}

    slope = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x

    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    if ss_tot == 0:
        r_squared = 1.0  # a perfectly flat real series -- not undefined, genuinely no residual variance
    else:
        ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
        r_squared = 1 - ss_res / ss_tot

    if abs(slope) < STABLE_SLOPE_THRESHOLD:
        direction = "stable"
    elif slope > 0:
        direction = "increasing"
    else:
        direction = "decreasing"

    return {
        "direction": direction,
        "slope_per_hour": round(slope, 4),
        "r_squared": round(max(0.0, min(1.0, r_squared)), 4),
        "n_points": n,
    }


def compute_trends_by_corridor(corridors: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    return {location: compute_trend(points) for location, points in corridors.items()}
