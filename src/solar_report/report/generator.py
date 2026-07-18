"""Orchestrates report generation: prompt assembly -> LLM call -> template rendering.

The LLM produces the interpretive Markdown body; Jinja2 templates wrap it
with metadata (period, system, generation timestamp) and a footer, either
as Markdown or as a standalone HTML page.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

import markdown as markdown_lib
from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup

from solar_report.analysis.models import PeriodSummary
from solar_report.config import SystemConfig
from solar_report.llm.client import AnthropicClient
from solar_report.report.prompts import SYSTEM_PROMPT, build_user_prompt

_TEMPLATE_NAMES: dict[str, str] = {
    "markdown": "report.md.j2",
    "html": "report.html.j2",
}


def _markdown_filter(text: str) -> Markup:
    """Convert Markdown to HTML, marked safe so autoescaping leaves it intact."""
    return Markup(markdown_lib.markdown(text))


class ReportGenerator:
    """Generates a natural-language report from period aggregations via the LLM."""

    def __init__(self, client: AnthropicClient) -> None:
        self._client = client
        self._environment = Environment(
            loader=PackageLoader("solar_report.report", "templates"),
            autoescape=select_autoescape(enabled_extensions=("html.j2",)),
            keep_trailing_newline=True,
        )
        self._environment.filters["markdown"] = _markdown_filter

    async def generate(
        self,
        system: SystemConfig,
        summary: PeriodSummary,
        period_label: Literal["week", "month"],
        output_format: Literal["markdown", "html"] = "markdown",
        _body_override: str | None = None,
    ) -> str:
        """Build the prompts, call the LLM, and render the full report.

        ``_body_override`` is a test/dry-run hook: when provided, the LLM call
        is skipped and the given string is used as the report body directly.
        """
        if _body_override is not None:
            body_markdown = _body_override
        else:
            user_prompt = build_user_prompt(system, summary, period_label)
            body_markdown = await self._client.generate(
                system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt
            )
        template = self._environment.get_template(_TEMPLATE_NAMES[output_format])
        return template.render(
            system=system,
            summary=summary,
            body_markdown=body_markdown,
            generated_at=datetime.now(UTC),
        )
