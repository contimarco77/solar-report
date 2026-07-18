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
    threshold_pct: float = 15.0,
) -> list[str]:
    """Human-readable observations for days deviating from the baseline.

    A day is flagged when its production deviates from ``baseline_daily_kwh``
    by strictly more than ``threshold_pct`` percent in either direction, e.g.
    ``"Wednesday (2026-07-15) produced 8.2 kWh, 42% below the 4-week average
    of 14.1 kWh"``. The "4-week average" phrasing assumes the default
    ``compute_baseline`` window. Returns an empty list when nothing is notable
    or when ``baseline_daily_kwh`` is not positive (no meaningful comparison).
    """
    if baseline_daily_kwh <= 0:
        return []
    observations: list[str] = []
    for day, kwh in summary.daily_values:
        deviation_pct = (kwh - baseline_daily_kwh) / baseline_daily_kwh * 100.0
        if abs(deviation_pct) <= threshold_pct:
            continue
        direction = "below" if deviation_pct < 0 else "above"
        observations.append(
            f"{day.strftime('%A')} ({day.isoformat()}) produced {kwh:.1f} kWh, "
            f"{abs(deviation_pct):.0f}% {direction} the 4-week average "
            f"of {baseline_daily_kwh:.1f} kWh"
        )
    return observations
