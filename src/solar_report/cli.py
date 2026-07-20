"""Typer CLI entry point: ``solar-report generate``."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv

from solar_report.analysis.aggregations import period_start
from solar_report.analysis.models import EventRecord
from solar_report.analysis.pipeline import build_summary
from solar_report.config import Config, load_config
from solar_report.llm.client import AnthropicClient
from solar_report.report.generator import ReportGenerator
from solar_report.sources.base import DataSource
from solar_report.sources.csv_source import CsvDataSource, read_events_csv

app = typer.Typer(no_args_is_help=True)

BASELINE_WINDOW_DAYS = 28

DRY_RUN_BODY = """\
## Overview

This is a dry run: the LLM call was skipped and this placeholder replaces the
model-generated report body. Numbers in the metadata above come from the real
pipeline (source, aggregations, anomalies), so a successful dry run validates
everything except the Anthropic API call.
"""


class PeriodOption(StrEnum):
    week = "week"
    month = "month"


@app.callback()
def main() -> None:
    """Generate human-readable reports from solar PV production data."""


def _build_source(config: Config) -> DataSource:
    if config.source.kind == "csv":
        assert config.source.csv is not None  # guaranteed by SourceConfig validator
        return CsvDataSource(config.source.csv.path)
    typer.echo(
        "The home_assistant source is not implemented yet; use a csv source for now.",
        err=True,
    )
    raise typer.Exit(code=1)


@app.command()
def generate(
    config_path: Annotated[
        Path,
        typer.Option(
            "--config",
            exists=True,
            dir_okay=False,
            help="Path to the config YAML file.",
        ),
    ],
    period: Annotated[
        PeriodOption | None,
        typer.Option(
            "--period",
            help="Report period; overrides report.period from the config.",
        ),
    ] = None,
    reference: Annotated[
        str | None,
        typer.Option(
            "--reference",
            help="ISO date (YYYY-MM-DD) the period ends on, interpreted as UTC. Default: today.",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Skip the LLM call and use a placeholder report body (no API credits spent).",
        ),
    ] = False,
) -> None:
    """Generate a report for the period ending at the reference date."""
    load_dotenv()
    config = load_config(config_path)

    if reference is not None:
        try:
            reference_date = date.fromisoformat(reference)
        except ValueError as exc:
            raise typer.BadParameter(
                f"expected an ISO date (YYYY-MM-DD), got {reference!r}"
            ) from exc
        # End-of-day so the source read window covers the whole reference day.
        reference_dt = datetime.combine(reference_date, time.max, tzinfo=UTC)
    else:
        reference_dt = datetime.now(UTC)

    period_label = period.value if period is not None else config.report.period
    if period_label == "day":
        typer.echo(
            "Daily reports are not supported yet; use --period week or --period month.",
            err=True,
        )
        raise typer.Exit(code=1)

    source = _build_source(config)
    start_dt = datetime.combine(
        period_start(period_label, reference_dt.date()), time.min, tzinfo=UTC
    )
    points = source.read(start_dt, reference_dt)
    historical_points = source.read(start_dt - timedelta(days=BASELINE_WINDOW_DAYS), start_dt)

    events: list[EventRecord] | None = None
    if config.source.kind == "csv":
        assert config.source.csv is not None  # guaranteed by SourceConfig validator
        events_path = config.source.csv.events_path
        if events_path is not None:
            events = read_events_csv(events_path, start_dt, reference_dt)

    summary = build_summary(
        points, historical_points, period=period_label, reference=reference_dt, events=events
    )

    client = AnthropicClient(config.llm.api_key, config.llm.model, config.llm.max_tokens)
    generator = ReportGenerator(client)
    rendered = asyncio.run(
        generator.generate(
            system=config.system,
            summary=summary,
            period_label=period_label,
            output_format=config.report.output_format,
            language=config.report.language,
            _body_override=DRY_RUN_BODY if dry_run else None,
        )
    )

    suffix = ".html" if config.report.output_format == "html" else ".md"
    output_path = Path(
        config.report.output_path.replace("{period}", period_label).replace(
            "{date}", summary.end_date.isoformat()
        )
    ).with_suffix(suffix)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    typer.echo(str(output_path))
