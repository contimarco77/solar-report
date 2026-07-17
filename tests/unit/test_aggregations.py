"""Unit tests for aggregate_daily and summarize_period."""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from solar_report.analysis.aggregations import aggregate_daily, summarize_period
from solar_report.analysis.models import ProductionData

ROME = timezone(timedelta(hours=2))  # CEST, fixed offset for determinism


def _point(timestamp: datetime, production_wh: float) -> ProductionData:
    return ProductionData(timestamp=timestamp, production_wh=production_wh)


class TestAggregateDaily:
    def test_empty_input_returns_empty_list(self) -> None:
        assert aggregate_daily([]) == []

    def test_single_day_sums_and_converts_to_kwh(self) -> None:
        points = [
            _point(datetime(2026, 7, 14, 9, 0, tzinfo=UTC), 1200.0),
            _point(datetime(2026, 7, 14, 12, 0, tzinfo=UTC), 2500.0),
            _point(datetime(2026, 7, 14, 15, 0, tzinfo=UTC), 800.0),
        ]
        assert aggregate_daily(points) == [(date(2026, 7, 14), pytest.approx(4.5))]

    def test_multiple_days_sorted_by_date(self) -> None:
        points = [
            _point(datetime(2026, 7, 15, 12, 0, tzinfo=UTC), 2000.0),
            _point(datetime(2026, 7, 13, 12, 0, tzinfo=UTC), 1000.0),
            _point(datetime(2026, 7, 14, 12, 0, tzinfo=UTC), 3000.0),
        ]
        assert aggregate_daily(points) == [
            (date(2026, 7, 13), pytest.approx(1.0)),
            (date(2026, 7, 14), pytest.approx(3.0)),
            (date(2026, 7, 15), pytest.approx(2.0)),
        ]

    def test_day_boundary_depends_on_target_timezone(self) -> None:
        # 23:30 UTC on July 14 is already 01:30 on July 15 in UTC+2.
        points = [_point(datetime(2026, 7, 14, 23, 30, tzinfo=UTC), 1000.0)]

        assert aggregate_daily(points, tz=UTC) == [(date(2026, 7, 14), pytest.approx(1.0))]
        assert aggregate_daily(points, tz=ROME) == [(date(2026, 7, 15), pytest.approx(1.0))]

    def test_duplicate_timestamps_last_wins(self) -> None:
        points = [
            _point(datetime(2026, 7, 14, 12, 0, tzinfo=UTC), 1000.0),
            _point(datetime(2026, 7, 14, 12, 0, tzinfo=UTC), 3000.0),
        ]
        assert aggregate_daily(points) == [(date(2026, 7, 14), pytest.approx(3.0))]

    def test_duplicate_instants_across_offsets_last_wins(self) -> None:
        # 12:00 UTC and 14:00 UTC+2 are the same instant.
        points = [
            _point(datetime(2026, 7, 14, 12, 0, tzinfo=UTC), 1000.0),
            _point(datetime(2026, 7, 14, 14, 0, tzinfo=ROME), 3000.0),
        ]
        assert aggregate_daily(points) == [(date(2026, 7, 14), pytest.approx(3.0))]


class TestSummarizePeriod:
    REFERENCE = datetime(2026, 7, 17, 18, 0, tzinfo=UTC)

    def test_empty_input_returns_empty_summary_with_period_bounds(self) -> None:
        summary = summarize_period([], "week", self.REFERENCE)

        assert summary.start_date == date(2026, 7, 11)
        assert summary.end_date == date(2026, 7, 17)
        assert summary.total_kwh == 0.0
        assert summary.daily_values == []
        assert summary.best_day is None
        assert summary.worst_day is None

    def test_points_outside_window_yield_empty_summary(self) -> None:
        points = [_point(datetime(2026, 6, 1, 12, 0, tzinfo=UTC), 5000.0)]
        summary = summarize_period(points, "week", self.REFERENCE)

        assert summary.total_kwh == 0.0
        assert summary.daily_values == []
        assert summary.best_day is None

    def test_week_totals_and_best_worst_days(self) -> None:
        points = [
            _point(datetime(2026, 7, 12, 12, 0, tzinfo=UTC), 8000.0),
            _point(datetime(2026, 7, 13, 12, 0, tzinfo=UTC), 22000.0),
            _point(datetime(2026, 7, 14, 12, 0, tzinfo=UTC), 3000.0),
        ]
        summary = summarize_period(points, "week", self.REFERENCE)

        assert summary.start_date == date(2026, 7, 11)
        assert summary.end_date == date(2026, 7, 17)
        assert summary.total_kwh == pytest.approx(33.0)
        assert summary.daily_values == [
            (date(2026, 7, 12), pytest.approx(8.0)),
            (date(2026, 7, 13), pytest.approx(22.0)),
            (date(2026, 7, 14), pytest.approx(3.0)),
        ]
        assert summary.best_day == date(2026, 7, 13)
        assert summary.worst_day == date(2026, 7, 14)

    def test_best_worst_ties_resolve_to_earliest_date(self) -> None:
        points = [
            _point(datetime(2026, 7, 13, 12, 0, tzinfo=UTC), 5000.0),
            _point(datetime(2026, 7, 14, 12, 0, tzinfo=UTC), 5000.0),
        ]
        summary = summarize_period(points, "week", self.REFERENCE)

        assert summary.best_day == date(2026, 7, 13)
        assert summary.worst_day == date(2026, 7, 13)

    def test_day_period_covers_only_reference_date(self) -> None:
        points = [
            _point(datetime(2026, 7, 17, 12, 0, tzinfo=UTC), 4000.0),
            _point(datetime(2026, 7, 16, 12, 0, tzinfo=UTC), 9000.0),
        ]
        summary = summarize_period(points, "day", self.REFERENCE)

        assert summary.start_date == date(2026, 7, 17)
        assert summary.end_date == date(2026, 7, 17)
        assert summary.total_kwh == pytest.approx(4.0)

    def test_month_period_starts_day_after_same_day_previous_month(self) -> None:
        summary = summarize_period([], "month", self.REFERENCE)

        assert summary.start_date == date(2026, 6, 18)
        assert summary.end_date == date(2026, 7, 17)

    def test_month_period_clamps_when_previous_month_is_shorter(self) -> None:
        reference = datetime(2026, 3, 31, 12, 0, tzinfo=UTC)
        summary = summarize_period([], "month", reference)

        assert summary.start_date == date(2026, 3, 1)
        assert summary.end_date == date(2026, 3, 31)

    def test_days_bucketed_in_reference_timezone(self) -> None:
        # 23:30 UTC on July 17 is July 18 in UTC+2, outside a window
        # ending on the reference's calendar day (July 17 in UTC+2).
        late_point = _point(datetime(2026, 7, 17, 23, 30, tzinfo=UTC), 1000.0)
        reference_rome = datetime(2026, 7, 17, 18, 0, tzinfo=ROME)

        summary_utc = summarize_period([late_point], "day", self.REFERENCE)
        summary_rome = summarize_period([late_point], "day", reference_rome)

        assert summary_utc.total_kwh == pytest.approx(1.0)
        assert summary_rome.total_kwh == 0.0

    def test_window_end_uses_reference_local_calendar_day(self) -> None:
        # 23:30 UTC on July 17 is already July 18, 01:30 in UTC+2, so the
        # one-day window in that timezone is July 18.
        reference = datetime(2026, 7, 17, 23, 30, tzinfo=UTC).astimezone(ROME)
        summary = summarize_period([], "day", reference)

        assert summary.start_date == date(2026, 7, 18)
        assert summary.end_date == date(2026, 7, 18)

    def test_rejects_naive_reference(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            summarize_period([], "week", datetime(2026, 7, 17, 12, 0))
