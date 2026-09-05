"""Tests for the Weak-Signal / proactive layer (Slice 15 / spec section
10): a real least-squares trend over a corridor's own recorded risk
history -- "risk is increasing" as a description of the data, not a
forecast from a trained model with no labeled ground truth to learn a
forecast from.
"""

from datetime import datetime, timedelta

from app.services.weak_signal_service import compute_trend, compute_trends_by_corridor


def _points(scores, start=None, step_hours=1):
    start = start or datetime(2026, 1, 1)
    return [{"time": start + timedelta(hours=i * step_hours), "score": s} for i, s in enumerate(scores)]


class TestComputeTrend:
    def test_too_few_points_is_honestly_insufficient_not_a_guess(self):
        result = compute_trend(_points([10, 20]))
        assert result["direction"] == "insufficient_data"
        assert result["slope_per_hour"] is None

    def test_a_clean_rising_series_is_increasing_with_a_real_slope(self):
        result = compute_trend(_points([10, 20, 30, 40, 50]))
        assert result["direction"] == "increasing"
        assert result["slope_per_hour"] == 10.0
        assert result["r_squared"] == 1.0  # a perfect line -- real, not rounded up

    def test_a_clean_falling_series_is_decreasing(self):
        result = compute_trend(_points([80, 60, 40, 20, 0]))
        assert result["direction"] == "decreasing"
        assert result["slope_per_hour"] == -20.0

    def test_a_flat_series_is_stable(self):
        result = compute_trend(_points([30, 30, 30, 30]))
        assert result["direction"] == "stable"
        assert result["slope_per_hour"] == 0.0

    def test_tiny_real_fluctuation_still_reads_as_stable(self):
        # Real noise around a flat baseline shouldn't flip to
        # "increasing"/"decreasing" on every minor fluctuation.
        result = compute_trend(_points([30, 31, 29, 30, 31]))
        assert result["direction"] == "stable"

    def test_points_given_out_of_order_are_sorted_before_fitting(self):
        start = datetime(2026, 1, 1)
        shuffled = [
            {"time": start + timedelta(hours=2), "score": 30},
            {"time": start, "score": 10},
            {"time": start + timedelta(hours=1), "score": 20},
        ]
        result = compute_trend(shuffled)
        assert result["direction"] == "increasing"
        assert result["slope_per_hour"] == 10.0

    def test_iso_string_timestamps_are_accepted_not_just_datetimes(self):
        points = [
            {"time": "2026-01-01T00:00:00", "score": 10},
            {"time": "2026-01-01T01:00:00", "score": 20},
            {"time": "2026-01-01T02:00:00", "score": 30},
        ]
        result = compute_trend(points)
        assert result["direction"] == "increasing"

    def test_a_noisy_series_reports_a_real_low_r_squared(self):
        result = compute_trend(_points([10, 90, 5, 95, 8]))
        assert result["r_squared"] < 0.5


class TestComputeTrendsByCorridor:
    def test_computes_one_trend_per_corridor_independently(self):
        trends = compute_trends_by_corridor({
            "Suez Canal (Gulf of Suez)": _points([10, 20, 30, 40]),
            "Strait of Malacca": _points([40, 30, 20, 10]),
        })
        assert trends["Suez Canal (Gulf of Suez)"]["direction"] == "increasing"
        assert trends["Strait of Malacca"]["direction"] == "decreasing"

    def test_empty_input_returns_empty_output(self):
        assert compute_trends_by_corridor({}) == {}
