"""Unit tests for the consolidated analysis pipeline."""

from datetime import UTC, date, datetime, timedelta

from solar_report.analysis.models import EventRecord, ProductionData
from solar_report.analysis.pipeline import build_summary

REFERENCE = datetime(2026, 7, 12, 23, 0, tzinfo=UTC)
PERIOD_START = date(2026, 7, 6)


def _point(day: date, kwh: float) -> ProductionData:
    return ProductionData(
        timestamp=datetime(day.year, day.month, day.day, 12, 0, tzinfo=UTC),
        production_wh=kwh * 1000.0,
    )


def _steady_days(start: date, days: int, kwh: float) -> list[ProductionData]:
    return [_point(start + timedelta(days=offset), kwh) for offset in range(days)]


def _baseline_history(kwh: float) -> list[ProductionData]:
    """28 steady days ending the day before the reporting period starts."""
    return _steady_days(PERIOD_START - timedelta(days=28), days=28, kwh=kwh)


def test_empty_input_returns_empty_summary_with_empty_anomalies() -> None:
    summary = build_summary([], [], period="week", reference=REFERENCE)

    assert summary.start_date == PERIOD_START
    assert summary.end_date == date(2026, 7, 12)
    assert summary.daily_values == []
    assert summary.total_kwh == 0.0
    assert summary.best_day is None
    assert summary.worst_day is None
    assert summary.baseline_daily_kwh == 0.0
    assert summary.anomalies == []
    assert summary.events == []


def test_events_default_to_empty_when_not_passed() -> None:
    points = _steady_days(PERIOD_START, days=7, kwh=20.0)

    summary = build_summary(points, _baseline_history(20.0), period="week", reference=REFERENCE)

    assert summary.events == []


def test_events_are_attached_to_the_summary() -> None:
    points = _steady_days(PERIOD_START, days=7, kwh=20.0)
    events = [
        EventRecord(
            timestamp=datetime(2026, 7, 8, 14, 30, tzinfo=UTC),
            severity="warning",
            code="INV-042",
            message="Inverter derating detected",
        )
    ]

    summary = build_summary(
        points, _baseline_history(20.0), period="week", reference=REFERENCE, events=events
    )

    assert summary.events == events


def test_clear_anomaly_is_detected_and_attached() -> None:
    points = _steady_days(PERIOD_START, days=7, kwh=20.0)
    points[2] = _point(date(2026, 7, 8), 8.0)  # 60% below the 20 kWh baseline

    summary = build_summary(points, _baseline_history(20.0), period="week", reference=REFERENCE)

    assert summary.baseline_daily_kwh == 20.0
    assert len(summary.anomalies) == 1
    assert summary.anomalies[0].day == date(2026, 7, 8)


def test_no_anomaly_when_production_matches_baseline() -> None:
    points = _steady_days(PERIOD_START, days=7, kwh=20.0)

    summary = build_summary(points, _baseline_history(20.0), period="week", reference=REFERENCE)

    assert summary.baseline_daily_kwh == 20.0
    assert summary.anomalies == []
    assert summary.total_kwh == 140.0


def test_baseline_warning_set_with_limited_history() -> None:
    points = _steady_days(PERIOD_START, days=7, kwh=20.0)
    history = _steady_days(PERIOD_START - timedelta(days=5), days=5, kwh=20.0)

    summary = build_summary(points, history, period="week", reference=REFERENCE)

    assert summary.baseline_warning == (
        "Baseline computed on only 5 days of historical data. "
        "Accuracy will improve as more history accumulates."
    )


def test_no_baseline_warning_with_ample_history() -> None:
    points = _steady_days(PERIOD_START, days=7, kwh=20.0)
    history = _steady_days(PERIOD_START - timedelta(days=30), days=30, kwh=20.0)

    summary = build_summary(points, history, period="week", reference=REFERENCE)

    assert summary.baseline_warning is None


def test_baseline_window_excludes_the_reporting_period() -> None:
    # History contains 28 good days before the period plus a huge day inside
    # the period: the latter must not inflate the baseline.
    history = _baseline_history(20.0) + [_point(date(2026, 7, 7), 100.0)]
    points = _steady_days(PERIOD_START, days=7, kwh=20.0)

    summary = build_summary(points, history, period="week", reference=REFERENCE)

    assert summary.baseline_daily_kwh == 20.0
    assert summary.anomalies == []
