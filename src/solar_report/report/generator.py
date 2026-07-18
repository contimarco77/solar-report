"""Orchestrates report generation: prompt assembly -> LLM call -> raw Markdown.

Template rendering (Jinja2, Markdown/HTML output) is a separate concern
handled by a later module; this one returns the LLM output as-is.
"""

from __future__ import annotations

from typing import Literal

from solar_report.analysis.models import PeriodSummary
from solar_report.config import SystemConfig
from solar_report.llm.client import AnthropicClient
from solar_report.report.prompts import SYSTEM_PROMPT, build_user_prompt


class ReportGenerator:
    """Generates a natural-language report from period aggregations via the LLM."""

    def __init__(self, client: AnthropicClient) -> None:
        self._client = client

    async def generate(
        self,
        system: SystemConfig,
        summary: PeriodSummary,
        period_label: Literal["week", "month"],
    ) -> str:
        """Build the prompts, call the LLM, and return the raw Markdown report."""
        user_prompt = build_user_prompt(system, summary, period_label)
        return await self._client.generate(
            system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt
        )
