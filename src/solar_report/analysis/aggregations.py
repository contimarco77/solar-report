"""Pure aggregation functions: production points to daily values and period summaries."""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta, tzinfo
from typing import Literal

from solar_report.analysis.models import PeriodSummary, ProductionData

Period = Literal["day", "week", "month"]


def aggregate_daily(points: list[ProductionData], tz: tzinfo = UTC) -> list[tuple[date, float]]:
    """Sum production per calendar day, converted to kWh, sorted by date.

    Points are bucketed by the calendar day of their timestamp converted to
    ``tz`` (UTC by default). Points whose timestamps denote the same instant
    (regardless of UTC offset) are deduplicated with last-wins semantics: the
    point appearing last in ``points`` replaces earlier ones.
    """
    deduplicated: dict[datetime, float] = {}
    for point in points:
        deduplicated[point.timestamp] = point.production_wh
    totals: defaultdict[date, float] = defaultdict(float)
    for timestamp, production_wh in deduplicated.items():
        totals[timestamp.astimezone(tz).date()] += production_wh
    return sorted((day, wh / 1000.0) for day, wh in totals.items())


def summarize_period(
    points: list[ProductionData],
    period: Period,
    reference: datetime,
) -> PeriodSummary:
    """Summarize production for the period ending at ``reference``.

    The window covers whole calendar days in the timezone of ``reference``
    (which must be timezone-aware) and ends on the reference's calendar day,
    inclusive: 1 day for ``"day"``, 7 days for ``"week"``, and for ``"month"``
    it starts the day after the same calendar day of the previous month
    (clamped to that month's length).

    Days without any recorded point are omitted from ``daily_values`` rather
    than reported as zero, so missing data stays distinguishable from zero
    production. When no point falls inside the window (including an empty
    ``points`` list), an empty summary is returned: ``total_kwh=0.0``,
    ``daily_values=[]``, ``best_day``/``worst_day`` set to ``None``, with
    ``start_date``/``end_date`` still set to the period bounds. Ties for
    best/worst day resolve to the earliest date.
    """
    if reference.tzinfo is None:
        raise ValueError("reference must be timezone-aware")
    end = reference.date()
    start = _period_start(period, end)
    daily_values = [
        (day, kwh)
        for day, kwh in aggregate_daily(points, tz=reference.tzinfo)
        if start <= day <= end
    ]
    if not daily_values:
        return PeriodSummary(
            start_date=start,
            end_date=end,
            total_kwh=0.0,
            daily_values=[],
            best_day=None,
            worst_day=None,
        )
    best_day, _ = max(daily_values, key=lambda item: item[1])
    worst_day, _ = min(daily_values, key=lambda item: item[1])
    return PeriodSummary(
        start_date=start,
        end_date=end,
        total_kwh=sum(kwh for _, kwh in daily_values),
        daily_values=daily_values,
        best_day=best_day,
        worst_day=worst_day,
    )


def _period_start(period: Period, end: date) -> date:
    """First calendar day of the period ending on ``end`` (inclusive)."""
    if period == "day":
        return end
    if period == "week":
        return end - timedelta(days=6)
    previous_year, previous_month = (
        (end.year, end.month - 1) if end.month > 1 else (end.year - 1, 12)
    )
    days_in_previous_month = monthrange(previous_year, previous_month)[1]
    same_day_previous_month = date(
        previous_year, previous_month, min(end.day, days_in_previous_month)
    )
    return same_day_previous_month + timedelta(days=1)
