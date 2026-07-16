"""Pydantic models for the solar-report config YAML and loading helpers.

Secrets are never stored in config files: string values may reference
environment variables with ``${VAR_NAME}`` syntax, resolved at load time.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

_ENV_VAR_PATTERN = re.compile(r"\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}")


class _StrictModel(BaseModel):
    """Base model that rejects unknown keys, so config typos fail loudly."""

    model_config = ConfigDict(extra="forbid")


class SystemConfig(_StrictModel):
    name: str
    location: str | None = None
    installed_kwp: float = Field(gt=0)
    panels: int | None = Field(default=None, gt=0)
    tilt_deg: float | None = Field(default=None, ge=0, le=90)
    azimuth_deg: float | None = Field(default=None, ge=0, le=360)


class HomeAssistantConfig(_StrictModel):
    url: str
    token: str
    entity_id: str


class CsvConfig(_StrictModel):
    path: Path


class SourceConfig(_StrictModel):
    kind: Literal["home_assistant", "csv"]
    home_assistant: HomeAssistantConfig | None = None
    csv: CsvConfig | None = None

    @model_validator(mode="after")
    def _selected_kind_is_configured(self) -> SourceConfig:
        if getattr(self, self.kind) is None:
            raise ValueError(
                f"source.kind is {self.kind!r} but the source.{self.kind} section is missing"
            )
        return self


class ReportConfig(_StrictModel):
    period: Literal["day", "week", "month"] = "week"
    tone: Literal["friendly", "technical", "brief"] = "friendly"
    language: Literal["en"] = "en"
    output_format: Literal["markdown", "html"] = "markdown"
    output_path: str = "./reports/{period}-{date}.md"


class LlmConfig(_StrictModel):
    provider: Literal["anthropic"] = "anthropic"
    model: str = "claude-sonnet-5"
    api_key: str
    max_tokens: int = Field(default=1500, gt=0)


class Config(_StrictModel):
    system: SystemConfig
    source: SourceConfig
    report: ReportConfig = ReportConfig()
    llm: LlmConfig


def _interpolate_env(value: Any) -> Any:
    """Recursively replace ``${VAR}`` references in string values."""
    if isinstance(value, str):

        def replace(match: re.Match[str]) -> str:
            name = match.group("name")
            resolved = os.environ.get(name)
            if resolved is None:
                raise ValueError(f"environment variable {name!r} referenced in config is not set")
            return resolved

        return _ENV_VAR_PATTERN.sub(replace, value)
    if isinstance(value, dict):
        return {key: _interpolate_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_interpolate_env(item) for item in value]
    return value


def load_config(path: str | Path) -> Config:
    """Load, env-interpolate, and validate a YAML config file."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"config file {path} must contain a YAML mapping")
    return Config.model_validate(_interpolate_env(raw))
