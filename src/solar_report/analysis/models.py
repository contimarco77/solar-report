"""Data models for production time-series points and period aggregations."""

from __future__ import annotations

from datetime import date

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProductionData(_StrictModel):
    """A single production time-series point.

    ``production_wh`` is the incremental energy produced during the measurement
    interval leading up to ``timestamp``, in watt-hours — NOT a cumulative meter
    reading. Aggregations sum these values, so cumulative readings (e.g. Home
    Assistant ``total_increasing`` sensors, Solar-Log daily counters) must be
    converted to incremental values by the data source before instantiating
    ``ProductionData``.
    """

    timestamp: AwareDatetime
    production_wh: float = Field(ge=0)
    """Incremental energy (Wh) for the interval ending at ``timestamp``."""
    panel_breakdown: dict[str, float] | None = None
    """Optional per-panel production in Wh, keyed by panel identifier."""

    @field_validator("production_wh")
    @classmethod
    def _reject_negative_production(cls, value: float) -> float:
        if value < 0:
            raise ValueError("production_wh must not be negative")
        return value

    @field_validator("panel_breakdown")
    @classmethod
    def _reject_negative_panel_values(
        cls, value: dict[str, float] | None
    ) -> dict[str, float] | None:
        if value is not None:
            for panel_id, wh in value.items():
                if wh < 0:
                    raise ValueError(f"panel {panel_id!r} has negative production: {wh}")
        return value


class PeriodSummary(_StrictModel):
    """Aggregated production stats for a reporting period."""

    start_date: date
    end_date: date
    total_kwh: float = Field(ge=0)
    daily_values: list[tuple[date, float]]
    best_day: date | None
    """Date with the highest production, or None when the period has no data."""
    worst_day: date | None
    """Date with the lowest production, or None when the period has no data."""
    baseline_kwh_avg: float | None = Field(default=None, ge=0)
    """Rolling-baseline daily average (kWh) for deviation comparisons."""

    @field_validator("daily_values")
    @classmethod
    def _reject_negative_daily_values(
        cls, value: list[tuple[date, float]]
    ) -> list[tuple[date, float]]:
        for day, kwh in value:
            if kwh < 0:
                raise ValueError(f"day {day.isoformat()} has negative production: {kwh}")
        return value

    @model_validator(mode="after")
    def _check_date_order(self) -> PeriodSummary:
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self

    @classmethod
    def from_daily_values(
        cls,
        daily_values: list[tuple[date, float]],
        baseline_kwh_avg: float | None = None,
    ) -> PeriodSummary:
        """Build a summary from per-day values, computing totals and best/worst days."""
        if not daily_values:
            raise ValueError("daily_values must not be empty")
        ordered = sorted(daily_values)
        best_day, _ = max(ordered, key=lambda item: item[1])
        worst_day, _ = min(ordered, key=lambda item: item[1])
        return cls(
            start_date=ordered[0][0],
            end_date=ordered[-1][0],
            total_kwh=sum(kwh for _, kwh in ordered),
            daily_values=ordered,
            best_day=best_day,
            worst_day=worst_day,
            baseline_kwh_avg=baseline_kwh_avg,
        )
