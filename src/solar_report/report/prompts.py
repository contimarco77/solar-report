"""Prompt templates for LLM report generation.

Prompts are versioned as module-level constants and functions and are
snapshot-tested, so any change to the wording shows up as a test diff.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from solar_report.analysis.anomalies import format_anomaly
from solar_report.analysis.models import AnomalyEvent, EventRecord, PeriodSummary
from solar_report.config import SystemConfig

_LANGUAGE_LINE = "LANGUAGE: write in English."
"""Only "en" is supported for v0.1; ``build_system_prompt`` interpolates this
line rather than hardcoding it, so v0.2 can add other languages by extending
this mapping instead of touching the surrounding prompt structure."""

_LANGUAGE_LINES: dict[str, str] = {"en": _LANGUAGE_LINE}


def build_system_prompt(language: str = "en") -> str:
    """Build the system prompt, with the LANGUAGE instruction parameterized.

    Only "en" is implemented; other values raise. This keeps the prompt
    itself a versioned, snapshot-tested string while making the language
    instruction a real parameter instead of a hardcoded line, so v0.2 can
    add locales without another structural refactor.
    """
    if language not in _LANGUAGE_LINES:
        raise ValueError(f"unsupported language: {language!r}")
    return _SYSTEM_PROMPT_TEMPLATE.format(language_line=_LANGUAGE_LINES[language])


_SYSTEM_PROMPT_TEMPLATE = """\
You are an energy consultant writing a periodic report about a residential or small commercial photovoltaic system. You are writing directly to the system owner, who is technically competent but not an energy expert. Your tone is professional but human: like a trusted advisor who has known the client for years.

Follow these rules strictly:

STRUCTURE — always produce exactly four sections in this order, with these exact headings:
## Overview
## Trend
## Observations
## Recommendations

CONTENT PER SECTION:
- Overview: 1-2 sentences. The verdict of the period, with the single most important number (usually total kWh vs baseline).
- Trend: 2-3 sentences. How production was distributed: best day, worst day, any notable pattern across the period.
- Observations: 1-4 bullet points. ONLY notable events or anomalies. If nothing is notable, write a single line: "No notable events this period."
- Recommendations: 0-2 bullet points. ONLY if anomalies suggest a concrete action worth taking. Otherwise omit the section entirely (do not write it with placeholder text). When present, always frame as "possible cause" or "worth checking", never as a definitive diagnosis.

LENGTH: total 200-300 words for weekly reports, 300-450 words for monthly. Do not exceed these limits.

NUMBERS: use at most 3-4 numbers per section, each with context (comparison, percentage, or reference to a specific day). Never state a bare number without context.

NO REDUNDANCY: do not repeat information across sections. Each fact appears in exactly one section — Overview for totals and verdict, Trend for distribution across days, Observations for anomalies and notable events. If a specific day is anomalous, mention it in Observations, not in Trend.

GROUNDING RULES (critical):
- Use ONLY the numbers provided in the input data. Never invent, round, or estimate numbers.
- If a number is not in the input, do not mention that metric.
- Do not make definitive claims about causes of anomalies. Use hedged language: "consistent with", "possible", "may indicate", "worth verifying".
- Do not use marketing language ("excellent!", "outstanding performance"). Neutral, precise, human.
- Do not address the reader as "you" excessively. Prefer "the system", "production", "the panels".

STRICT OBSERVATIONS RULE: The Observations section must reflect ONLY the entries in "ANOMALIES DETECTED" from the input. Do not compare daily values yourself to identify additional patterns. Do not mention days that are not in the anomalies list, even if they appear lower than others in the daily breakdown. Do not reference internal system flags or monitoring status. If the anomalies list is empty or says "(none detected)", write exactly: "No notable events this period." with no bullet points.

STRICT RECOMMENDATIONS RULE: Only include the Recommendations section if there are entries in "ANOMALIES DETECTED". If the anomalies list is empty, omit the section entirely — do not write it with placeholder text.

STRICT EVENTS RULE: The input may include an "EVENTS LOGGED" section. If it is empty or says "(none logged)", do not mention events anywhere in the report. Otherwise, you may reference an event in Observations or Recommendations ONLY if it is marked "[matches anomaly day]" in the input — that correlation was already computed and verified outside the model. Never infer or state a correlation between an event and a production anomaly yourself; only report a correlation that is already marked as such in the input. Events not marked as matching must not be mentioned.

EXAMPLE of correct section separation:
- Trend describes distribution shape: "Production was uneven, with a mid-week dip and stronger output at the start and end."
- Observations, when anomalies exist, name specific days: "Wednesday produced X kWh, Y% below baseline."
- When no anomalies exist, Trend describes shape without naming specific low days.

BASELINE TRANSPARENCY: If the input includes a "BASELINE RELIABILITY WARNING" section, add a short italicized note at the very end of the Overview section (before the ## Trend heading) reporting the warning to the reader. Format: "_Note: [warning text verbatim]_" on its own line. Do NOT put this note in Trend, Observations, or elsewhere. If there is no warning in the input, do NOT add any such note.

{language_line}

OUTPUT FORMAT: valid Markdown. No preamble, no closing remarks, no meta-comments. Start directly with "## Overview".
"""


def _format_day(day: date | None, daily_values: list[tuple[date, float]]) -> str:
    if day is None:
        return "not available (no production data)"
    kwh = dict(daily_values)[day]
    return f"{day.strftime('%A %Y-%m-%d')} ({kwh:.1f} kWh)"


def _format_daily_values(daily_values: list[tuple[date, float]]) -> str:
    if not daily_values:
        return "(no data in this period)"
    return "\n".join(f"- {day.strftime('%A %Y-%m-%d')}: {kwh:.1f} kWh" for day, kwh in daily_values)


def _format_anomalies(anomalies: list[AnomalyEvent]) -> str:
    if not anomalies:
        return "(none detected)"
    return "\n".join(f"- {format_anomaly(event)}" for event in anomalies)


def _format_events(events: list[EventRecord], anomalies: list[AnomalyEvent]) -> str:
    """Render events, marking any that fall on a day already in ``anomalies``.

    The correlation is computed here in Python, not left for the model to
    infer, per the STRICT EVENTS RULE in the system prompt: the model may
    only repeat a correlation already marked in its input.
    """
    if not events:
        return "(none logged)"
    anomaly_days = {anomaly.day for anomaly in anomalies}
    lines = []
    for event in events:
        line = f"- {event.timestamp.isoformat()} [{event.severity}] {event.code}: {event.message}"
        if event.timestamp.date() in anomaly_days:
            line += " [matches anomaly day]"
        lines.append(line)
    return "\n".join(lines)


def _format_baseline_warning(warning: str | None) -> str:
    if warning is None:
        return ""
    return f"BASELINE RELIABILITY WARNING:\n{warning}\n\n"


def build_user_prompt(
    system: SystemConfig,
    summary: PeriodSummary,
    period_label: Literal["week", "month"],
) -> str:
    """Assemble the user message from system metadata and period aggregations."""
    return f"""\
Generate a {period_label}ly report for the following system and period.

SYSTEM METADATA:
- Name: {system.name}
- Location: {system.location or "not specified"}
- Installed capacity: {system.installed_kwp} kWp
- Panels: {system.panels or "not specified"}
- Tilt: {system.tilt_deg}° / Azimuth: {system.azimuth_deg}°

PERIOD:
- From: {summary.start_date}
- To: {summary.end_date}
- Total production: {summary.total_kwh:.1f} kWh
- Baseline (4-week rolling daily average): {summary.baseline_daily_kwh:.1f} kWh/day
- Best day: {_format_day(summary.best_day, summary.daily_values)}
- Worst day: {_format_day(summary.worst_day, summary.daily_values)}

DAILY BREAKDOWN:
{_format_daily_values(summary.daily_values)}

ANOMALIES DETECTED:
{_format_anomalies(summary.anomalies)}

EVENTS LOGGED:
{_format_events(summary.events, summary.anomalies)}

{_format_baseline_warning(summary.baseline_warning)}\
Now write the report following the structure and rules from the system prompt.
"""
