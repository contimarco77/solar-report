"""Unit test for config loading from a minimal valid YAML fixture."""

from pathlib import Path

import pytest

from solar_report.config import load_config

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_load_minimal_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")

    config = load_config(FIXTURES / "config-minimal.yaml")

    assert config.system.name == "Test PV"
    assert config.system.installed_kwp == 6.0
    assert config.source.kind == "csv"
    assert config.source.csv is not None
    assert config.source.csv.path == Path("./data/production.csv")
    assert config.source.csv.events_path is None
    # env var interpolation resolved the ${ANTHROPIC_API_KEY} reference
    assert config.llm.api_key == "test-key-123"
    # defaults applied for sections/fields not present in the minimal YAML
    assert config.report.period == "week"
    assert config.report.output_format == "markdown"
    assert config.llm.provider == "anthropic"
    assert config.llm.max_tokens == 1500


def test_csv_events_path_is_optional_and_can_be_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """\
system:
  name: "Test PV"
  installed_kwp: 6.0
source:
  kind: "csv"
  csv:
    path: "./data/production.csv"
    events_path: "./data/events.csv"
llm:
  api_key: "${ANTHROPIC_API_KEY}"
""",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.source.csv is not None
    assert config.source.csv.events_path == Path("./data/events.csv")
