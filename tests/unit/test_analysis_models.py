"""Unit tests for ProductionData and PeriodSummary."""

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from solar_report.analysis.models import PeriodSummary, ProductionData


class TestProductionData:
    def test_valid_construction(self) -> None:
        point = ProductionData(
            timestamp=datetime(2026, 7, 14, 12, 0, tzinfo=UTC),
            production_wh=1250.5,
            panel_breakdown={"panel_1": 620.0, "panel_2": 630.5},
        )
        assert point.production_wh == 1250.5
        assert point.panel_breakdown is not None
        assert point.panel_breakdown["panel_1"] == 620.0

    def test_panel_breakdown_is_optional(self) -> None:
        point = ProductionData(
            timestamp=datetime(2026, 7, 14, 12, 0, tzinfo=UTC),
            production_wh=0.0,
        )
        assert point.panel_breakdown is None

    def test_rejects_naive_timestamp(self) -> None:
        with pytest.raises(ValidationError):
            ProductionData(timestamp=datetime(2026, 7, 14, 12, 0), production_wh=100.0)

    def test_rejects_negative_production(self) -> None:
        with pytest.raises(ValidationError):
            ProductionData(
                timestamp=datetime(2026, 7, 14, 12, 0, tzinfo=UTC),
                production_wh=-1.0,
            )

    def test_rejects_negative_panel_value(self) -> None:
        with pytest.raises(ValidationError, match="panel_2"):
            ProductionData(
                timestamp=datetime(2026, 7, 14, 12, 0, tzinfo=UTC),
                production_wh=100.0,
                panel_breakdown={"panel_1": 100.0, "panel_2": -5.0},
            )


class TestPeriodSummary:
    DAILY = [
        (date(2026, 7, 7), 18.2),
        (date(2026, 7, 8), 22.5),
        (date(2026, 7, 9), 9.1),
    ]

    def test_valid_construction(self) -> None:
        summary = PeriodSummary(
            start_date=date(2026, 7, 7),
            end_date=date(2026, 7, 9),
            total_kwh=49.8,
            daily_values=self.DAILY,
            best_day=date(2026, 7, 8),
            worst_day=date(2026, 7, 9),
            baseline_kwh_avg=17.0,
        )
        assert summary.total_kwh == 49.8
        assert summary.baseline_kwh_avg == 17.0

    def test_rejects_negative_daily_value(self) -> None:
        with pytest.raises(ValidationError, match="2026-07-08"):
            PeriodSummary(
                start_date=date(2026, 7, 7),
                end_date=date(2026, 7, 9),
                total_kwh=10.0,
                daily_values=[(date(2026, 7, 7), 15.0), (date(2026, 7, 8), -2.0)],
                best_day=date(2026, 7, 7),
                worst_day=date(2026, 7, 8),
            )

    def test_rejects_end_date_before_start_date(self) -> None:
        with pytest.raises(ValidationError, match="end_date"):
            PeriodSummary(
                start_date=date(2026, 7, 9),
                end_date=date(2026, 7, 7),
                total_kwh=10.0,
                daily_values=self.DAILY,
                best_day=date(2026, 7, 8),
                worst_day=date(2026, 7, 9),
            )

    def test_from_daily_values_computes_totals(self) -> None:
        summary = PeriodSummary.from_daily_values(self.DAILY, baseline_kwh_avg=17.0)

        assert summary.start_date == date(2026, 7, 7)
        assert summary.end_date == date(2026, 7, 9)
        assert summary.total_kwh == pytest.approx(49.8)
        assert summary.best_day == date(2026, 7, 8)
        assert summary.worst_day == date(2026, 7, 9)
        assert summary.baseline_kwh_avg == 17.0

    def test_from_daily_values_rejects_empty_input(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            PeriodSummary.from_daily_values([])
