"""Unit tests for ReportGenerator with the LLM client mocked at the boundary."""

from datetime import date
from unittest.mock import AsyncMock

from solar_report.analysis.models import PeriodSummary
from solar_report.config import SystemConfig
from solar_report.llm.client import AnthropicClient
from solar_report.report.generator import ReportGenerator
from solar_report.report.prompts import SYSTEM_PROMPT

SYSTEM = SystemConfig(
    name="My rooftop PV",
    location="Turin, Italy",
    installed_kwp=6.0,
    panels=15,
    tilt_deg=30,
    azimuth_deg=180,
)

SUMMARY = PeriodSummary(
    start_date=date(2026, 7, 6),
    end_date=date(2026, 7, 7),
    total_kwh=46.4,
    daily_values=[(date(2026, 7, 6), 21.4), (date(2026, 7, 7), 25.0)],
    best_day=date(2026, 7, 7),
    worst_day=date(2026, 7, 6),
    baseline_daily_kwh=22.0,
    anomalies=["Production on 2026-07-06 was 15% below the rolling baseline"],
)

FAKE_REPORT = "## Overview\nA solid week for the system.\n"


async def test_generate_wraps_llm_output_in_template() -> None:
    client = AsyncMock(spec=AnthropicClient)
    client.generate.return_value = FAKE_REPORT
    generator = ReportGenerator(client)

    result = await generator.generate(SYSTEM, SUMMARY, period_label="week")

    assert result.startswith("# Solar Report — My rooftop PV")
    assert FAKE_REPORT.strip() in result


async def test_generate_calls_client_with_expected_prompts() -> None:
    client = AsyncMock(spec=AnthropicClient)
    client.generate.return_value = FAKE_REPORT
    generator = ReportGenerator(client)

    await generator.generate(SYSTEM, SUMMARY, period_label="week")

    client.generate.assert_awaited_once()
    kwargs = client.generate.await_args.kwargs
    assert kwargs["system_prompt"] == SYSTEM_PROMPT

    user_prompt = kwargs["user_prompt"]
    assert user_prompt.startswith("Generate a weekly report")
    assert "- Name: My rooftop PV\n" in user_prompt
    assert "- Total production: 46.4 kWh\n" in user_prompt
    assert "- Baseline (4-week rolling daily average): 22.0 kWh/day\n" in user_prompt
    assert "- Production on 2026-07-06 was 15% below the rolling baseline" in user_prompt
