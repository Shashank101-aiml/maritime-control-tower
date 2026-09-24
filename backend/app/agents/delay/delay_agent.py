"""Delay Intelligence Agent: how long real ocean legs on a lane take, and how
often they run late.

This replaces a shipment-delay classifier that was trained on an anonymized
supply-chain sample (PLANT08, PORT09, ...) unrelated to any real port, and
that reported an implausible 0.996 ROC-AUC. It answers a maritime question
from real data instead: for a lane between two real ports, what have real
container journeys actually taken?

The evidence is data/features/transit_journeys.csv -- real container legs
(pipeline/build_transit_journeys.py), each the days between loading and
discharge. For a lane the agent reports the empirical distribution of those
days (typical, planning worst-case, spread), how often journeys ran a week or
more past the lane's median, and how that moved over time -- and, where the
digital twin covers the lane, how the real transit compares with the ideal
sailing time plus the port congestion and live sea-state risk right now.

It deliberately does NOT emit a model score. pipeline/backtest_transit_models.py
tests, out of time, whether LightGBM or logistic regression on distance,
season and real weekly port congestion can beat "what this lane usually
does". On this data they cannot, and the saved backtest says so; a
prediction that can't beat the lane's own history would be a made-up number.
"""

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from app.core.logging import get_logger
from app.twin.coordinates import PORT_COORDINATES
from app.twin.digital_twin import get_digital_twin

logger = get_logger(__name__)

_ROOT = Path(__file__).resolve().parents[4]
JOURNEYS_PATH = _ROOT / "data" / "features" / "transit_journeys.csv"
SUMMARY_PATH = _ROOT / "data" / "features" / "transit_journeys_summary.json"
METRICS_PATH = _ROOT / "models" / "saved_models" / "delay_metrics.json"

# A lane needs at least this many recorded journeys before its statistics
# are offered -- fewer and a "typical" figure is anecdote.
MIN_LANE_JOURNEYS = 15
DELAY_THRESHOLDS_DAYS = (7, 10)
# Months with fewer journeys than this are left off the trend rather than
# plotted from two or three containers.
MIN_MONTH_JOURNEYS = 3
MIN_SEASON_JOURNEYS = 8

# Journey port name -> the digital twin's name for the same place.
TWIN_PORT_NAMES = {
    "Yantian": "Shenzhen",
    "Nansha": "Guangzhou",
    "Jawaharlal Nehru": "Nhava Sheva (Mumbai)",
    "Jebel Ali": "Dubai (Jebel Ali)",
    "Antwerpen": "Antwerp",
}


def twin_port_name(port: str) -> Optional[str]:
    name = TWIN_PORT_NAMES.get(port, port)
    return name if name in PORT_COORDINATES else None


def _num(value: Any, digits: int = 1) -> Optional[float]:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else round(f, digits)


class DelayAgent:
    def __init__(
        self,
        journeys_path: Path = JOURNEYS_PATH,
        summary_path: Path = SUMMARY_PATH,
        metrics_path: Path = METRICS_PATH,
    ) -> None:
        self._journeys = self._load_journeys(journeys_path)
        self._summary = self._load_json(summary_path)
        self._metrics = self._load_json(metrics_path)

    @staticmethod
    def _load_journeys(path: Path) -> Optional[pd.DataFrame]:
        try:
            df = pd.read_csv(path, parse_dates=["loaded_on", "discharged_on"])
        except (FileNotFoundError, ValueError) as exc:
            logger.warning("Transit journeys not found/usable at %s: %s", path, exc)
            return None
        df["lane"] = df["origin"] + " > " + df["destination"]
        return df

    @staticmethod
    def _load_json(path: Path) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(path.read_text())
        except (FileNotFoundError, ValueError):
            return None

    @property
    def is_available(self) -> bool:
        return self._journeys is not None

    # -- lanes -----------------------------------------------------------

    def _lane_rows(self, origin: str, destination: str) -> pd.DataFrame:
        if self._journeys is None:
            raise RuntimeError("Transit journey data is not available.")
        return self._journeys[(self._journeys["origin"] == origin) & (self._journeys["destination"] == destination)]

    def validate_lane(self, origin: str, destination: str) -> int:
        """Journey count for the lane, or ValueError if it can't support statistics."""
        n = len(self._lane_rows(origin, destination))
        if n == 0:
            raise ValueError(f"No recorded journeys from {origin} to {destination}.")
        if n < MIN_LANE_JOURNEYS:
            raise ValueError(
                f"Only {n} recorded journeys from {origin} to {destination}; "
                f"at least {MIN_LANE_JOURNEYS} are needed before the statistics mean anything."
            )
        return n

    def overview(self) -> Dict[str, Any]:
        if self._journeys is None:
            raise RuntimeError("Transit journey data is not available.")
        df = self._journeys
        grouped = df.groupby(["origin", "destination"])["ocean_days"].agg(["count", "median"]).reset_index()
        usable = grouped[grouped["count"] >= MIN_LANE_JOURNEYS].sort_values("count", ascending=False)

        destinations_by_origin: Dict[str, List[Dict[str, Any]]] = {}
        for _, row in usable.iterrows():
            destinations_by_origin.setdefault(row["origin"], []).append({
                "destination": row["destination"],
                "journeys": int(row["count"]),
                "median_days": _num(row["median"]),
            })

        return {
            "journeys": int(len(df)),
            "lanes_recorded": int(len(grouped)),
            "lanes_usable": int(len(usable)),
            "min_lane_journeys": MIN_LANE_JOURNEYS,
            "loaded_from": df["loaded_on"].min().strftime("%Y-%m-%d"),
            "loaded_to": df["loaded_on"].max().strftime("%Y-%m-%d"),
            "origins": sorted(destinations_by_origin),
            "destinations_by_origin": destinations_by_origin,
            "data_quality": self._summary,
            "backtest": self._metrics,
        }

    # -- one lane --------------------------------------------------------

    def assess(
        self,
        origin: str,
        destination: str,
        loading_date: Optional[date] = None,
        live_corridor_scores: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        n = self.validate_lane(origin, destination)
        rows = self._lane_rows(origin, destination)
        days = rows["ocean_days"]
        median = float(days.median())

        delayed = {}
        for threshold in DELAY_THRESHOLDS_DAYS:
            count = int((days >= median + threshold).sum())
            delayed[str(threshold)] = {"journeys": count, "share": round(count / n, 3)}

        by_month = rows.assign(month=rows["loaded_on"].dt.to_period("M").astype(str)).groupby("month")["ocean_days"]
        monthly = [
            {"month": month, "journeys": int(group.count()), "median_days": _num(group.median())}
            for month, group in by_month
            if group.count() >= MIN_MONTH_JOURNEYS
        ]

        season = None
        if loading_date is not None:
            same = rows[rows["loaded_on"].dt.month == loading_date.month]["ocean_days"]
            if len(same) >= MIN_SEASON_JOURNEYS:
                season = {"calendar_month": loading_date.month, "journeys": int(len(same)), "median_days": _num(same.median())}

        confidence = round(0.65 + 0.30 * min(1.0, n / 50), 2)
        return {
            "method": "lane_statistics",
            "origin": origin,
            "destination": destination,
            "loading_date": loading_date.isoformat() if loading_date else None,
            "journeys": n,
            "loaded_from": rows["loaded_on"].min().strftime("%Y-%m-%d"),
            "loaded_to": rows["loaded_on"].max().strftime("%Y-%m-%d"),
            "transit_days": {
                "median": _num(median),
                "mean": _num(days.mean()),
                "p10": _num(days.quantile(0.10)),
                "p25": _num(days.quantile(0.25)),
                "p75": _num(days.quantile(0.75)),
                "p90": _num(days.quantile(0.90)),
                "min": int(days.min()),
                "max": int(days.max()),
            },
            "delayed": delayed,
            "monthly": monthly,
            "same_season": season,
            "context": self._twin_context(origin, destination, median, live_corridor_scores),
            "confidence": confidence,
            "confidence_basis": f"Based on {n} recorded journeys on this lane; it reaches its ceiling at 50.",
            "caveats": [
                "Statistics describe what these journeys actually took. They are not a forecast for a "
                "specific container, and they mostly cover 2021-2022, a period of severe port backlogs.",
                "Models using season, distance and port congestion were tested out of time and did not beat "
                "this lane's own history, so no model score is shown.",
            ],
        }

    def _twin_context(
        self,
        origin: str,
        destination: str,
        median_days: float,
        live_scores: Optional[Dict[str, int]],
    ) -> Dict[str, Any]:
        """What the digital twin knows about this lane today, where it covers it."""
        twin_origin, twin_destination = twin_port_name(origin), twin_port_name(destination)
        context: Dict[str, Any] = {
            "origin_port": self._port_snapshot(twin_origin),
            "destination_port": self._port_snapshot(twin_destination),
            "lane": None,
        }
        if not twin_origin or not twin_destination:
            return context

        try:
            twin = get_digital_twin()
            if live_scores is not None:
                twin.annotate_risk(live_scores)
            edges = twin.graph.get_edge_data(twin_origin, twin_destination) or {}
        except Exception as exc:
            logger.warning("Digital twin context unavailable for %s -> %s: %s", origin, destination, exc)
            return context

        if edges:
            lane_id, attrs = min(edges.items(), key=lambda item: item[1]["distance_nm"])
            context["lane"] = {
                "lane_id": lane_id,
                "distance_nm": attrs["distance_nm"],
                "ideal_transit_days": attrs["transit_days"],
                "ideal_basis": "distance at a typical 18-knot service speed (an assumption, not observed data)",
                "typical_extra_days": _num(median_days - attrs["transit_days"]),
                "risk": attrs.get("risk") if live_scores is not None else None,
                "risk_reason": attrs.get("risk_reason") if live_scores is not None else None,
            }
        return context

    @staticmethod
    def _port_snapshot(port: Optional[str]) -> Optional[Dict[str, Any]]:
        if port is None:
            return None
        try:
            node = get_digital_twin().graph.nodes[port]
        except Exception:
            return None
        snapshot: Dict[str, Any] = {"twin_name": port, "has_congestion_data": bool(node.get("has_congestion_data"))}
        if node.get("has_congestion_data"):
            snapshot.update({
                "congestion_index": _num(node.get("congestion_index"), 2),
                "congestion_percentile": node.get("congestion_percentile"),
                "avg_wait_days": _num(node.get("avg_wait_days")),
                "berth_delay_hrs": _num(node.get("berth_delay_hrs")),
                "as_of": node.get("metrics_as_of"),
            })
        return snapshot


_shared_agent: Optional[DelayAgent] = None


def get_delay_agent() -> DelayAgent:
    global _shared_agent
    if _shared_agent is None:
        _shared_agent = DelayAgent()
    return _shared_agent
