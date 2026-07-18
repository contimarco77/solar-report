"""Unit tests for compute_baseline and detect_anomalies."""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from solar_report.analysis.anomalies import compute_baseline, detect_anomalies
from solar_report.analysis.models import PeriodSummary, ProductionData

ROME = timezone(timedelta(hours=2))  # CEST, fixed offset for determinism

REFERENCE = datetime(2026, 7, 15, 8, 0, tzinfo=UTC)


def _point(timestamp: datetime, production_wh: float) -> ProductionData:
    return ProductionData(timestamp=timestamp, production_wh=production_wh)


def _summary(daily_values: list[tuple[date, float]]) -> PeriodSummary:
    return PeriodSummary.from_daily_values(daily_values)


class TestComputeBaseline:
    def test_empty_historical_returns_zero(self) -> None:
        assert compute_baseline([], REFERENCE) == 0.0

    def test_no_points_inside_window_returns_zero(self) -> None:
        outside = REFERENCE - timedelta(days=40)
        assert compute_baseline([_point(outside, 5000.0)], REFERENCE) == 0.0

    def test_average_over_multi_day_input(self) -> None:
        points = [
            _point(datetime(2026, 7, 12, 12, 0, tzinfo=UTC), 10_000.0),
            _point(datetime(2026, 7, 13, 12, 0, tzinfo=UTC), 12_000.0),
            _point(datetime(2026, 7, 14, 9, 0, tzinfo=UTC), 6_000.0),
            _point(datetime(2026, 7, 14, 15, 0, tzinfo=UTC), 8_000.0),
        ]
        # Days: 10.0, 12.0, 14.0 kWh -> average 12.0.
        assert compute_baseline(points, REFERENCE) == pytest.approx(12.0)

    def test_reference_day_excluded_from_window(self) -> None:
        points = [
            _point(datetime(2026, 7, 14, 12, 0, tzinfo=UTC), 10_000.0),
            _point(REFERENCE, 99_000.0),
        ]
        assert compute_baseline(points, REFERENCE) == pytest.approx(10.0)

    def test_days_older_than_window_excluded(self) -> None:
        points = [
            _point(datetime(2026, 7, 14, 12, 0, tzinfo=UTC), 10_000.0),
            # 2026-06-16 is 29 days before the reference day: outside a 28-day window.
            _point(datetime(2026, 6, 16, 12, 0, tzinfo=UTC), 99_000.0),
        ]
        assert compute_baseline(points, REFERENCE) == pytest.approx(10.0)

    def test_missing_days_do_not_deflate_average(self) -> None:
        points = [
            _point(datetime(2026, 7, 10, 12, 0, tzinfo=UTC), 10_000.0),
            _point(datetime(2026, 7, 14, 12, 0, tzinfo=UTC), 14_000.0),
        ]
        # Only two days have data: average is 12.0, not (10 + 14) / 28.
        assert compute_baseline(points, REFERENCE) == pytest.approx(12.0)

    def test_window_bucketing_uses_reference_timezone(self) -> None:
        # 23:30 UTC on July 14 is 01:30 on July 15 in UTC+2, i.e. on the
        # reference day itself, which is excluded from the window.
        points = [_point(datetime(2026, 7, 14, 23, 30, tzinfo=UTC), 10_000.0)]
        reference_rome = datetime(2026, 7, 15, 8, 0, tzinfo=ROME)
        assert compute_baseline(points, reference_rome) == 0.0
        assert compute_baseline(points, REFERENCE) == pytest.approx(10.0)

    def test_naive_reference_raises(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            compute_baseline([], datetime(2026, 7, 15, 8, 0))

    def test_non_positive_window_raises(self) -> None:
        with pytest.raises(ValueError, match="window_days"):
            compute_baseline([], REFERENCE, window_days=0)


class TestDetectAnomalies:
    def test_zero_baseline_returns_empty(self) -> None:
        summary = _summary([(date(2026, 7, 15), 8.2)])
        assert detect_anomalies(summary, baseline_daily_kwh=0.0) == []

    def test_empty_period_returns_empty(self) -> None:
        summary = PeriodSummary(
            start_date=date(2026, 7, 9),
            end_date=date(2026, 7, 15),
            total_kwh=0.0,
            daily_values=[],
            best_day=None,
            worst_day=None,
        )
        assert detect_anomalies(summary, baseline_daily_kwh=14.1) == []

    def test_day_below_threshold_flagged(self) -> None:
        summary = _summary([(date(2026, 7, 15), 8.2)])  # a Wednesday
        observations = detect_anomalies(summary, baseline_daily_kwh=14.1)
        assert observations == [
            "Wednesday (2026-07-15) produced 8.2 kWh, 42% below the 4-week average of 14.1 kWh"
        ]

    def test_day_above_threshold_flagged(self) -> None:
        summary = _summary([(date(2026, 7, 15), 18.0)])
        observations = detect_anomalies(summary, baseline_daily_kwh=14.1)
        assert len(observations) == 1
        assert "28% above the 4-week average of 14.1 kWh" in observations[0]

    def test_day_within_threshold_not_flagged(self) -> None:
        summary = _summary([(date(2026, 7, 15), 13.0)])  # ~8% below baseline
        assert detect_anomalies(summary, baseline_daily_kwh=14.1) == []

    def test_deviation_exactly_at_threshold_not_flagged(self) -> None:
        summary = _summary([(date(2026, 7, 15), 8.5)])  # exactly 15% below 10.0
        assert detect_anomalies(summary, baseline_daily_kwh=10.0) == []

    def test_best_and_worst_day_within_threshold_not_flagged(self) -> None:
        summary = _summary(
            [
                (date(2026, 7, 13), 9.5),
                (date(2026, 7, 14), 10.0),
                (date(2026, 7, 15), 10.5),
            ]
        )
        assert summary.best_day == date(2026, 7, 15)
        assert summary.worst_day == date(2026, 7, 13)
        assert detect_anomalies(summary, baseline_daily_kwh=10.0) == []

    def test_only_deviating_days_flagged_in_mixed_period(self) -> None:
        summary = _summary(
            [
                (date(2026, 7, 13), 4.0),
                (date(2026, 7, 14), 10.0),
                (date(2026, 7, 15), 10.5),
            ]
        )
        observations = detect_anomalies(summary, baseline_daily_kwh=10.0)
        assert len(observations) == 1
        assert observations[0].startswith("Monday (2026-07-13) produced 4.0 kWh")

    def test_custom_threshold_respected(self) -> None:
        summary = _summary([(date(2026, 7, 15), 9.0)])  # 10% below baseline
        assert detect_anomalies(summary, baseline_daily_kwh=10.0) == []
        assert len(detect_anomalies(summary, baseline_daily_kwh=10.0, threshold_pct=5.0)) == 1
