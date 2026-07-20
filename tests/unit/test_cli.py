"""CLI tests with the data source and LLM boundary mocked."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from solar_report.analysis.models import EventRecord, ProductionData
from solar_report.analysis.pipeline import build_summary
from solar_report.cli import DRY_RUN_BODY, app

runner = CliRunner()

REFERENCE = "2026-07-19"

WEEK_POINTS = [
    ProductionData(
        timestamp=datetime(2026, 7, 13, 12, tzinfo=UTC) + timedelta(days=offset),
        production_wh=21_600.0,
    )
    for offset in range(7)
]


def _write_config(tmp_path: Path, events_path: Path | None = None, **report_overrides: str) -> Path:
    report = {
        "period": "week",
        "output_format": "markdown",
        "output_path": str(tmp_path / "reports" / "{period}-{date}.md"),
    }
    report.update(report_overrides)
    report_yaml = "\n".join(f'  {key}: "{value}"' for key, value in report.items())
    events_line = f'    events_path: "{events_path}"\n' if events_path is not None else ""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""\
system:
  name: "My rooftop PV"
  location: "Turin, Italy"
  installed_kwp: 6.0
source:
  kind: "csv"
  csv:
    path: "{tmp_path / "production.csv"}"
{events_line}report:
{report_yaml}
llm:
  api_key: "${{ANTHROPIC_API_KEY}}"
""",
        encoding="utf-8",
    )
    return config_path


@pytest.fixture(autouse=True)
def _api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


def _fake_source() -> MagicMock:
    source = MagicMock()
    source.read.return_value = WEEK_POINTS
    return source


def test_dry_run_writes_report_without_calling_the_llm(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    source = _fake_source()
    client = MagicMock()
    client.generate = AsyncMock()

    with (
        patch("solar_report.cli._build_source", return_value=source),
        patch("solar_report.cli.AnthropicClient", return_value=client) as client_cls,
    ):
        result = runner.invoke(
            app,
            ["generate", "--config", str(config_path), "--reference", REFERENCE, "--dry-run"],
        )

    assert result.exit_code == 0, result.output
    client_cls.assert_called_once_with("test-key", "claude-sonnet-5", 1500)
    client.generate.assert_not_awaited()

    output_path = tmp_path / "reports" / "week-2026-07-19.md"
    assert str(output_path) in result.output
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert content.startswith("# Solar Report — My rooftop PV")
    assert "**Period:** 2026-07-13 to 2026-07-19" in content
    assert DRY_RUN_BODY.strip() in content


def test_reads_period_and_baseline_windows_from_source(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    source = _fake_source()

    with (
        patch("solar_report.cli._build_source", return_value=source),
        patch("solar_report.cli.AnthropicClient"),
    ):
        result = runner.invoke(
            app,
            ["generate", "--config", str(config_path), "--reference", REFERENCE, "--dry-run"],
        )

    assert result.exit_code == 0, result.output
    assert source.read.call_count == 2
    period_call, baseline_call = source.read.call_args_list

    period_from, period_to = period_call.args
    assert period_from == datetime(2026, 7, 13, tzinfo=UTC)
    assert period_to.date().isoformat() == REFERENCE
    assert period_to.tzinfo == UTC

    baseline_from, baseline_to = baseline_call.args
    assert baseline_from == datetime(2026, 7, 13, tzinfo=UTC) - timedelta(days=28)
    assert baseline_to == datetime(2026, 7, 13, tzinfo=UTC)


@pytest.mark.parametrize(
    ("output_format", "expected_name"),
    [("markdown", "week-2026-07-19.md"), ("html", "week-2026-07-19.html")],
)
def test_output_extension_follows_output_format(
    tmp_path: Path, output_format: str, expected_name: str
) -> None:
    config_path = _write_config(
        tmp_path,
        output_format=output_format,
        output_path=str(tmp_path / "reports" / "{period}-{date}"),
    )

    with (
        patch("solar_report.cli._build_source", return_value=_fake_source()),
        patch("solar_report.cli.AnthropicClient"),
    ):
        result = runner.invoke(
            app,
            ["generate", "--config", str(config_path), "--reference", REFERENCE, "--dry-run"],
        )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "reports" / expected_name).exists()


def test_html_format_overrides_md_suffix_in_path_template(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, output_format="html")

    with (
        patch("solar_report.cli._build_source", return_value=_fake_source()),
        patch("solar_report.cli.AnthropicClient"),
    ):
        result = runner.invoke(
            app,
            ["generate", "--config", str(config_path), "--reference", REFERENCE, "--dry-run"],
        )

    assert result.exit_code == 0, result.output
    output_path = tmp_path / "reports" / "week-2026-07-19.html"
    assert output_path.exists()
    assert not (tmp_path / "reports" / "week-2026-07-19.md").exists()
    assert output_path.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_period_option_overrides_config(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)

    with (
        patch("solar_report.cli._build_source", return_value=_fake_source()),
        patch("solar_report.cli.AnthropicClient"),
    ):
        result = runner.invoke(
            app,
            [
                "generate",
                "--config",
                str(config_path),
                "--period",
                "month",
                "--reference",
                REFERENCE,
                "--dry-run",
            ],
        )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "reports" / "month-2026-07-19.md").exists()


def test_generate_without_dry_run_uses_the_generator_body(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    generator = MagicMock()
    generator.generate = AsyncMock(return_value="rendered report")

    with (
        patch("solar_report.cli._build_source", return_value=_fake_source()),
        patch("solar_report.cli.AnthropicClient"),
        patch("solar_report.cli.ReportGenerator", return_value=generator),
    ):
        result = runner.invoke(
            app,
            ["generate", "--config", str(config_path), "--reference", REFERENCE],
        )

    assert result.exit_code == 0, result.output
    generator.generate.assert_awaited_once()
    kwargs = generator.generate.await_args.kwargs
    assert kwargs["_body_override"] is None
    assert kwargs["period_label"] == "week"
    assert kwargs["output_format"] == "markdown"
    assert kwargs["summary"].end_date.isoformat() == REFERENCE
    output_path = tmp_path / "reports" / "week-2026-07-19.md"
    assert output_path.read_text(encoding="utf-8") == "rendered report"


def test_invalid_reference_fails_with_error(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)

    with patch("solar_report.cli._build_source", return_value=_fake_source()):
        result = runner.invoke(
            app,
            ["generate", "--config", str(config_path), "--reference", "19/07/2026"],
        )

    assert result.exit_code != 0
    assert "ISO date" in result.output


def test_day_period_from_config_is_rejected(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, period="day")

    with patch("solar_report.cli._build_source", return_value=_fake_source()):
        result = runner.invoke(
            app,
            ["generate", "--config", str(config_path), "--reference", REFERENCE, "--dry-run"],
        )

    assert result.exit_code == 1
    assert "not supported" in result.output


def test_events_path_reads_events_in_the_reporting_period_window(tmp_path: Path) -> None:
    events_path = tmp_path / "events.csv"
    config_path = _write_config(tmp_path, events_path=events_path)
    events = [
        EventRecord(
            timestamp=datetime(2026, 7, 15, 14, 30, tzinfo=UTC),
            severity="warning",
            code="INV-042",
            message="Inverter derating detected",
        )
    ]

    with (
        patch("solar_report.cli._build_source", return_value=_fake_source()),
        patch("solar_report.cli.AnthropicClient"),
        patch("solar_report.cli.read_events_csv", return_value=events) as read_events,
        patch("solar_report.cli.build_summary", wraps=build_summary) as build_summary_spy,
    ):
        result = runner.invoke(
            app,
            ["generate", "--config", str(config_path), "--reference", REFERENCE, "--dry-run"],
        )

    assert result.exit_code == 0, result.output
    read_events.assert_called_once_with(
        events_path,
        datetime(2026, 7, 13, tzinfo=UTC),
        datetime.fromisoformat(f"{REFERENCE}T23:59:59.999999+00:00"),
    )
    assert build_summary_spy.call_args.kwargs["events"] == events


def test_no_events_path_means_no_events_read(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)

    with (
        patch("solar_report.cli._build_source", return_value=_fake_source()),
        patch("solar_report.cli.AnthropicClient"),
        patch("solar_report.cli.read_events_csv") as read_events,
    ):
        result = runner.invoke(
            app,
            ["generate", "--config", str(config_path), "--reference", REFERENCE, "--dry-run"],
        )

    assert result.exit_code == 0, result.output
    read_events.assert_not_called()
