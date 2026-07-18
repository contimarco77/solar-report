"""Pure anomaly-detection functions: baseline comparison and per-day deviations."""

from __future__ import annotations

from datetime import datetime, timedelta

from solar_report.analysis.aggregations import aggregate_daily
from solar_report.analysis.models import PeriodSummary, ProductionData


def compute_baseline(
    historical_points: list[ProductionData],
    reference: datetime,
    window_days: int = 28,
) -> float:
    """Rolling average daily production (kWh) over the window preceding ``reference``.

    The window covers the ``window_days`` whole calendar days immediately before
    the calendar day of ``reference`` (which must be timezone-aware), in the
    reference's timezone. The reference day itself is excluded so a period
    ending at ``reference`` is not averaged into its own baseline. Days without
    any recorded point are omitted from the average rather than counted as
    zero, so missing data does not deflate the baseline. Returns ``0.0`` when
    no point falls inside the window.
    """
    if reference.tzinfo is None:
        raise ValueError("reference must be timezone-aware")
    if window_days < 1:
        raise ValueError("window_days must be positive")
    end = reference.date() - timedelta(days=1)
    start = end - timedelta(days=window_days - 1)
    daily_kwh = [
        kwh
        for day, kwh in aggregate_daily(historical_points, tz=reference.tzinfo)
        if start <= day <= end
    ]
    if not daily_kwh:
        return 0.0
    return sum(daily_kwh) / len(daily_kwh)


def detect_anomalies(
    summary: PeriodSummary,
    baseline_daily_kwh: float,
    threshold_pct: float = 25.0,
) -> list[str]:
    """Human-readable observations for days underperforming the baseline.

    A day is flagged only when its production falls below
    ``baseline_daily_kwh`` by strictly more than ``threshold_pct`` percent,
    e.g. ``"Wednesday (2026-07-15) produced 8.2 kWh, 41.8% below the 4-week
    average of 14.1 kWh"``. Days above baseline are never flagged: for health
    monitoring they are just good weather, not anomalies. Conservative default
    to avoid flagging normal weather variability. Only surfaces genuine
    deviations worth investigating. The "4-week average" phrasing assumes the
    default ``compute_baseline`` window. Returns an empty list when nothing is
    notable or when ``baseline_daily_kwh`` is not positive (no meaningful
    comparison).
    """
    if baseline_daily_kwh <= 0:
        return []
    observations: list[str] = []
    for day, kwh in summary.daily_values:
        deficit_pct = (baseline_daily_kwh - kwh) / baseline_daily_kwh * 100.0
        if deficit_pct <= threshold_pct:
            continue
        observations.append(
            f"{day.strftime('%A')} ({day.isoformat()}) produced {kwh:.1f} kWh, "
            f"{deficit_pct:.1f}% below the 4-week average "
            f"of {baseline_daily_kwh:.1f} kWh"
        )
    return observations
