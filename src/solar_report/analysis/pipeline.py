"""Analysis pipeline: aggregation, baseline, and anomaly detection in one call.

Consolidates the summarize_period -> compute_baseline -> detect_anomalies
sequence so callers cannot forget to attach anomalies or pick an inconsistent
baseline reference.
"""

from __future__ import annotations

from datetime import datetime, time

from solar_report.analysis.aggregations import Period, summarize_period
from solar_report.analysis.anomalies import compute_baseline, detect_anomalies
from solar_report.analysis.models import PeriodSummary, ProductionData


def build_summary(
    points: list[ProductionData],
    historical_points: list[ProductionData],
    period: Period,
    reference: datetime,
) -> PeriodSummary:
    """Summarize the period ending at ``reference`` with baseline and anomalies attached.

    The baseline window ends the day before ``summary.start_date``, so the
    reporting period is never averaged into its own baseline
    (``compute_baseline`` excludes its reference day, hence the reference
    passed to it is ``start_date`` itself). The returned summary always has
    ``baseline_daily_kwh`` set and ``anomalies`` populated (empty list when
    nothing is notable or no baseline is available).
    """
    summary = summarize_period(points, period=period, reference=reference)
    baseline_reference = datetime.combine(summary.start_date, time.min, tzinfo=reference.tzinfo)
    baseline_daily_kwh = compute_baseline(historical_points, reference=baseline_reference)
    anomalies = detect_anomalies(summary, baseline_daily_kwh)
    return summary.model_copy(
        update={"baseline_daily_kwh": baseline_daily_kwh, "anomalies": anomalies}
    )
