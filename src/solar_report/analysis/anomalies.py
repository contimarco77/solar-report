"""Pure anomaly-detection functions: baseline comparison and per-day deviations."""

from __future__ import annotations

from datetime import datetime, timedelta

from solar_report.analysis.aggregations import aggregate_daily
from solar_report.analysis.models import AnomalyEvent, PeriodSummary, ProductionData


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
) -> list[AnomalyEvent]:
    """Detect days underperforming the baseline, as data (no rendered text).

    A day is flagged only when its production falls below
    ``baseline_daily_kwh`` by strictly more than ``threshold_pct`` percent.
    Days above baseline are never flagged: for health monitoring they are
    just good weather, not anomalies. Conservative default to avoid flagging
    normal weather variability. Only surfaces genuine deviations worth
    investigating. Returns an empty list when nothing is notable or when
    ``baseline_daily_kwh`` is not positive (no meaningful comparison).
    """
    if baseline_daily_kwh <= 0:
        return []
    events: list[AnomalyEvent] = []
    for day, kwh in summary.daily_values:
        deficit_pct = (baseline_daily_kwh - kwh) / baseline_daily_kwh * 100.0
        if deficit_pct <= threshold_pct:
            continue
        events.append(
            AnomalyEvent(
                day=day,
                kwh=kwh,
                pct_below=deficit_pct,
                baseline_kwh=baseline_daily_kwh,
            )
        )
    return events


def format_anomaly(event: AnomalyEvent, language: str = "en") -> str:
    """Render an ``AnomalyEvent`` as a human-readable observation string.

    Only English is implemented for v0.1 (``language`` is otherwise unused);
    the parameter exists so the v0.2 translation work is a matter of adding
    branches here, not re-plumbing every caller. Kept next to
    ``detect_anomalies`` rather than in a separate ``i18n`` module: there is
    a single presentation function today, and colocating it with the data it
    renders keeps the diff small until a second locale actually justifies a
    dedicated module.

    Produces e.g. ``"Wednesday (2026-07-15) produced 8.2 kWh, 41.8% below the
    4-week average of 14.1 kWh"``. The "4-week average" phrasing assumes the
    default ``compute_baseline`` window.
    """
    return (
        f"{event.day.strftime('%A')} ({event.day.isoformat()}) produced {event.kwh:.1f} kWh, "
        f"{event.pct_below:.1f}% below the 4-week average "
        f"of {event.baseline_kwh:.1f} kWh"
    )
