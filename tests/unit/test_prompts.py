"""Snapshot tests for the user prompt builder.

These assert exact string output on purpose: any wording change in the
prompt must show up as an explicit test diff.
"""

from datetime import date

from solar_report.analysis.models import PeriodSummary
from solar_report.config import SystemConfig
from solar_report.report.prompts import SYSTEM_PROMPT, build_user_prompt

FULL_SYSTEM = SystemConfig(
    name="My rooftop PV",
    location="Turin, Italy",
    installed_kwp=6.0,
    panels=15,
    tilt_deg=30,
    azimuth_deg=180,
)

WEEK_DAILY_VALUES = [
    (date(2026, 7, 6), 21.4),
    (date(2026, 7, 7), 25.0),
    (date(2026, 7, 8), 12.3),
    (date(2026, 7, 9), 24.8),
    (date(2026, 7, 10), 26.1),
    (date(2026, 7, 11), 23.0),
    (date(2026, 7, 12), 22.4),
]


def test_system_prompt_starts_and_ends_as_expected() -> None:
    assert SYSTEM_PROMPT.startswith("You are an energy consultant")
    assert SYSTEM_PROMPT.rstrip().endswith('Start directly with "## Overview".')


def test_weekly_prompt_with_anomalies() -> None:
    summary = PeriodSummary(
        start_date=date(2026, 7, 6),
        end_date=date(2026, 7, 12),
        total_kwh=155.0,
        daily_values=WEEK_DAILY_VALUES,
        best_day=date(2026, 7, 10),
        worst_day=date(2026, 7, 8),
        baseline_daily_kwh=23.5,
        anomalies=["Production on 2026-07-08 dropped 47% below the rolling baseline"],
    )
    prompt = build_user_prompt(FULL_SYSTEM, summary, period_label="week")
    assert prompt == (
        "Generate a weekly report for the following system and period.\n"
        "\n"
        "SYSTEM METADATA:\n"
        "- Name: My rooftop PV\n"
        "- Location: Turin, Italy\n"
        "- Installed capacity: 6.0 kWp\n"
        "- Panels: 15\n"
        "- Tilt: 30.0° / Azimuth: 180.0°\n"
        "\n"
        "PERIOD:\n"
        "- From: 2026-07-06\n"
        "- To: 2026-07-12\n"
        "- Total production: 155.0 kWh\n"
        "- Baseline (4-week rolling daily average): 23.5 kWh/day\n"
        "- Best day: Friday 2026-07-10 (26.1 kWh)\n"
        "- Worst day: Wednesday 2026-07-08 (12.3 kWh)\n"
        "\n"
        "DAILY BREAKDOWN:\n"
        "- Monday 2026-07-06: 21.4 kWh\n"
        "- Tuesday 2026-07-07: 25.0 kWh\n"
        "- Wednesday 2026-07-08: 12.3 kWh\n"
        "- Thursday 2026-07-09: 24.8 kWh\n"
        "- Friday 2026-07-10: 26.1 kWh\n"
        "- Saturday 2026-07-11: 23.0 kWh\n"
        "- Sunday 2026-07-12: 22.4 kWh\n"
        "\n"
        "ANOMALIES DETECTED:\n"
        "- Production on 2026-07-08 dropped 47% below the rolling baseline\n"
        "\n"
        "Now write the report following the structure and rules from the system prompt.\n"
    )


def test_weekly_prompt_without_anomalies_and_optional_metadata() -> None:
    system = SystemConfig(name="Bare PV", installed_kwp=3.2, tilt_deg=25, azimuth_deg=170)
    summary = PeriodSummary(
        start_date=date(2026, 7, 6),
        end_date=date(2026, 7, 8),
        total_kwh=58.7,
        daily_values=WEEK_DAILY_VALUES[:3],
        best_day=date(2026, 7, 7),
        worst_day=date(2026, 7, 8),
        baseline_daily_kwh=20.0,
    )
    prompt = build_user_prompt(system, summary, period_label="week")
    assert prompt == (
        "Generate a weekly report for the following system and period.\n"
        "\n"
        "SYSTEM METADATA:\n"
        "- Name: Bare PV\n"
        "- Location: not specified\n"
        "- Installed capacity: 3.2 kWp\n"
        "- Panels: not specified\n"
        "- Tilt: 25.0° / Azimuth: 170.0°\n"
        "\n"
        "PERIOD:\n"
        "- From: 2026-07-06\n"
        "- To: 2026-07-08\n"
        "- Total production: 58.7 kWh\n"
        "- Baseline (4-week rolling daily average): 20.0 kWh/day\n"
        "- Best day: Tuesday 2026-07-07 (25.0 kWh)\n"
        "- Worst day: Wednesday 2026-07-08 (12.3 kWh)\n"
        "\n"
        "DAILY BREAKDOWN:\n"
        "- Monday 2026-07-06: 21.4 kWh\n"
        "- Tuesday 2026-07-07: 25.0 kWh\n"
        "- Wednesday 2026-07-08: 12.3 kWh\n"
        "\n"
        "ANOMALIES DETECTED:\n"
        "(none detected)\n"
        "\n"
        "Now write the report following the structure and rules from the system prompt.\n"
    )


def test_monthly_prompt_label() -> None:
    summary = PeriodSummary(
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 2),
        total_kwh=40.0,
        daily_values=[(date(2026, 6, 1), 19.0), (date(2026, 6, 2), 21.0)],
        best_day=date(2026, 6, 2),
        worst_day=date(2026, 6, 1),
        baseline_daily_kwh=18.3,
    )
    prompt = build_user_prompt(FULL_SYSTEM, summary, period_label="month")
    assert prompt.startswith("Generate a monthly report for the following system and period.\n")
    assert "- Best day: Tuesday 2026-06-02 (21.0 kWh)\n" in prompt
    assert "- Worst day: Monday 2026-06-01 (19.0 kWh)\n" in prompt


def test_prompt_with_empty_daily_values() -> None:
    summary = PeriodSummary(
        start_date=date(2026, 7, 6),
        end_date=date(2026, 7, 12),
        total_kwh=0.0,
        daily_values=[],
        best_day=None,
        worst_day=None,
    )
    prompt = build_user_prompt(FULL_SYSTEM, summary, period_label="week")
    assert "- Best day: not available (no production data)\n" in prompt
    assert "- Worst day: not available (no production data)\n" in prompt
    assert "DAILY BREAKDOWN:\n(no data in this period)\n" in prompt
    assert "ANOMALIES DETECTED:\n(none detected)\n" in prompt
