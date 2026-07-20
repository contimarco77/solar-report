"""CSV data source (see docs/csv-format.md for the expected file format)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import ValidationError

from solar_report.analysis.models import EventRecord, ProductionData

REQUIRED_COLUMNS = ("timestamp", "production_wh")
EVENTS_REQUIRED_COLUMNS = ("timestamp", "severity", "code", "message")


class CsvDataSource:
    """Reads production data from a CSV file.

    The file must have a header row with at least the columns ``timestamp``
    (ISO 8601 with timezone offset) and ``production_wh`` (non-negative float,
    incremental energy per interval — not a cumulative meter reading; see
    docs/csv-format.md). ``separator`` and ``decimal`` are configurable to
    support European exports (e.g. ``separator=";"`` with ``decimal=","``).
    """

    def __init__(self, path: str | Path, separator: str = ",", decimal: str = ".") -> None:
        self._path = Path(path)
        self._separator = separator
        self._decimal = decimal

    def read(self, start: datetime, end: datetime) -> list[ProductionData]:
        _require_aware(start, "start")
        _require_aware(end, "end")
        if end < start:
            raise ValueError("end must not be before start")

        try:
            frame = pd.read_csv(self._path, sep=self._separator, decimal=self._decimal)
        except pd.errors.EmptyDataError as exc:
            raise ValueError(f"CSV file {self._path} is empty") from exc

        missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
        if missing:
            raise ValueError(
                f"CSV file {self._path} is missing required columns: {', '.join(missing)}"
                f" (found: {', '.join(str(c) for c in frame.columns)})"
            )

        points: list[ProductionData] = []
        for offset, (_, row) in enumerate(frame.iterrows()):
            line = offset + 2  # 1-based, accounting for the header row
            timestamp = self._parse_timestamp(row["timestamp"], line)
            production_wh = self._parse_production(row["production_wh"], line)
            try:
                point = ProductionData(timestamp=timestamp, production_wh=production_wh)
            except ValidationError as exc:
                raise ValueError(f"{self._path}, line {line}: {exc}") from exc
            if start <= point.timestamp <= end:
                points.append(point)

        points.sort(key=lambda point: point.timestamp)
        return points

    def _parse_timestamp(self, raw: Any, line: int) -> datetime:
        if pd.isna(raw):
            raise ValueError(f"{self._path}, line {line}: missing timestamp")
        try:
            timestamp = datetime.fromisoformat(str(raw).strip())
        except ValueError as exc:
            raise ValueError(
                f"{self._path}, line {line}: timestamp {raw!r} is not valid ISO 8601"
            ) from exc
        if timestamp.tzinfo is None:
            raise ValueError(
                f"{self._path}, line {line}: timestamp {raw!r} has no timezone;"
                " timestamps must include an explicit offset,"
                " e.g. 2026-07-14T12:00:00+02:00 or 2026-07-14T10:00:00Z"
            )
        return timestamp

    def _parse_production(self, raw: Any, line: int) -> float:
        if pd.isna(raw):
            raise ValueError(f"{self._path}, line {line}: missing production_wh")
        try:
            return float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{self._path}, line {line}: production_wh {raw!r} is not a number;"
                " check the 'separator' and 'decimal' settings if this is a European export"
            ) from exc


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")


def _parse_event_timestamp(path: Path, raw: Any, line: int) -> datetime:
    if pd.isna(raw):
        raise ValueError(f"{path}, line {line}: missing timestamp")
    try:
        timestamp = datetime.fromisoformat(str(raw).strip())
    except ValueError as exc:
        raise ValueError(f"{path}, line {line}: timestamp {raw!r} is not valid ISO 8601") from exc
    if timestamp.tzinfo is None:
        raise ValueError(
            f"{path}, line {line}: timestamp {raw!r} has no timezone;"
            " timestamps must include an explicit offset,"
            " e.g. 2026-07-14T12:00:00+02:00 or 2026-07-14T10:00:00Z"
        )
    return timestamp


def read_events_csv(path: str | Path, start: datetime, end: datetime) -> list[EventRecord]:
    """Read vendor-reported events from an optional events CSV file.

    Independent of :class:`CsvDataSource`: the events schema (``timestamp,
    severity, code, message``, see docs/events-format.md) is unrelated to the
    production schema, so this is a plain function rather than a method on a
    production-data class. Mirrors ``CsvDataSource.read``'s parsing rules:
    timezone-aware timestamps only, inclusive ``[start, end]`` filtering,
    ascending sort, and error messages that identify the file and row.
    """
    path = Path(path)
    _require_aware(start, "start")
    _require_aware(end, "end")
    if end < start:
        raise ValueError("end must not be before start")

    try:
        frame = pd.read_csv(path)
    except pd.errors.EmptyDataError as exc:
        raise ValueError(f"CSV file {path} is empty") from exc

    missing = [column for column in EVENTS_REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(
            f"CSV file {path} is missing required columns: {', '.join(missing)}"
            f" (found: {', '.join(str(c) for c in frame.columns)})"
        )

    events: list[EventRecord] = []
    for offset, (_, row) in enumerate(frame.iterrows()):
        line = offset + 2  # 1-based, accounting for the header row
        timestamp = _parse_event_timestamp(path, row["timestamp"], line)
        try:
            event = EventRecord(
                timestamp=timestamp,
                severity=row["severity"],
                code=str(row["code"]),
                message=str(row["message"]),
            )
        except ValidationError as exc:
            raise ValueError(f"{path}, line {line}: {exc}") from exc
        if start <= event.timestamp <= end:
            events.append(event)

    events.sort(key=lambda event: event.timestamp)
    return events
