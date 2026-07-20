"""Unit tests for CsvDataSource."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from solar_report.sources.base import DataSource
from solar_report.sources.csv_source import CsvDataSource, read_events_csv

START = datetime(2026, 7, 14, 0, 0, tzinfo=UTC)
END = datetime(2026, 7, 14, 23, 59, tzinfo=UTC)


def write_csv(tmp_path: Path, content: str, name: str = "production.csv") -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_valid_csv(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "timestamp,production_wh\n"
        "2026-07-14T11:00:00+02:00,1810.0\n"
        "2026-07-14T10:00:00+02:00,1250.5\n",
    )
    source = CsvDataSource(path)

    points = source.read(START, END)

    assert isinstance(source, DataSource)
    assert len(points) == 2
    # sorted ascending even though the file is out of order
    assert points[0].production_wh == 1250.5
    assert points[0].timestamp == datetime.fromisoformat("2026-07-14T10:00:00+02:00")
    assert points[1].production_wh == 1810.0


def test_empty_file(tmp_path: Path) -> None:
    path = write_csv(tmp_path, "")

    with pytest.raises(ValueError, match="is empty"):
        CsvDataSource(path).read(START, END)


def test_header_only_file_returns_no_points(tmp_path: Path) -> None:
    path = write_csv(tmp_path, "timestamp,production_wh\n")

    assert CsvDataSource(path).read(START, END) == []


def test_missing_columns(tmp_path: Path) -> None:
    path = write_csv(tmp_path, "time,energy\n2026-07-14T10:00:00+02:00,1250.5\n")

    with pytest.raises(ValueError, match="missing required columns: timestamp, production_wh"):
        CsvDataSource(path).read(START, END)


def test_naive_timestamp_rejected(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "timestamp,production_wh\n2026-07-14T10:00:00,1250.5\n",
    )

    with pytest.raises(ValueError, match="line 2.*has no timezone"):
        CsvDataSource(path).read(START, END)


def test_out_of_window_rows_filtered(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "timestamp,production_wh\n"
        "2026-07-13T23:00:00+00:00,100.0\n"  # before window
        "2026-07-14T00:00:00+00:00,200.0\n"  # on start boundary (inclusive)
        "2026-07-14T12:00:00+00:00,300.0\n"  # inside
        "2026-07-15T00:00:00+00:00,400.0\n",  # after window
    )

    points = CsvDataSource(path).read(START, END)

    assert [p.production_wh for p in points] == [200.0, 300.0]


def test_malformed_production_rejected(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "timestamp,production_wh\n"
        "2026-07-14T10:00:00+02:00,1250.5\n"
        "2026-07-14T11:00:00+02:00,not-a-number\n",
    )

    with pytest.raises(ValueError, match="line 3.*is not a number"):
        CsvDataSource(path).read(START, END)


def test_negative_production_rejected(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "timestamp,production_wh\n2026-07-14T10:00:00+02:00,-5.0\n",
    )

    with pytest.raises(ValueError, match="line 2"):
        CsvDataSource(path).read(START, END)


def test_european_format(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "timestamp;production_wh\n"
        "2026-07-14T10:00:00+02:00;1250,5\n"
        "2026-07-14T11:00:00+02:00;1810,0\n",
    )

    points = CsvDataSource(path, separator=";", decimal=",").read(START, END)

    assert [p.production_wh for p in points] == [1250.5, 1810.0]


def test_naive_window_bounds_rejected(tmp_path: Path) -> None:
    path = write_csv(tmp_path, "timestamp,production_wh\n")

    with pytest.raises(ValueError, match="start must be a timezone-aware"):
        CsvDataSource(path).read(datetime(2026, 7, 14), END)


def write_events_csv(tmp_path: Path, content: str, name: str = "events.csv") -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_read_events_csv_valid(tmp_path: Path) -> None:
    path = write_events_csv(
        tmp_path,
        "timestamp,severity,code,message\n"
        "2026-07-14T11:00:00+02:00,warning,INV-042,Inverter derating detected\n"
        "2026-07-14T10:00:00+02:00,info,SYS-001,Scheduled maintenance check\n",
    )

    events = read_events_csv(path, START, END)

    assert len(events) == 2
    # sorted ascending even though the file is out of order
    assert events[0].code == "SYS-001"
    assert events[0].timestamp == datetime.fromisoformat("2026-07-14T10:00:00+02:00")
    assert events[1].code == "INV-042"
    assert events[1].severity == "warning"
    assert events[1].message == "Inverter derating detected"


def test_read_events_csv_missing_columns(tmp_path: Path) -> None:
    path = write_events_csv(tmp_path, "timestamp,severity\n2026-07-14T10:00:00+02:00,warning\n")

    with pytest.raises(ValueError, match="missing required columns:.*code.*message"):
        read_events_csv(path, START, END)


def test_read_events_csv_naive_timestamp_rejected(tmp_path: Path) -> None:
    path = write_events_csv(
        tmp_path,
        "timestamp,severity,code,message\n2026-07-14T10:00:00,warning,INV-042,Derating\n",
    )

    with pytest.raises(ValueError, match="line 2.*has no timezone"):
        read_events_csv(path, START, END)


def test_read_events_csv_rejects_invalid_severity(tmp_path: Path) -> None:
    path = write_events_csv(
        tmp_path,
        "timestamp,severity,code,message\n"
        "2026-07-14T10:00:00+02:00,critically-bad,INV-042,Derating\n",
    )

    with pytest.raises(ValueError, match="line 2"):
        read_events_csv(path, START, END)


def test_read_events_csv_out_of_window_rows_filtered(tmp_path: Path) -> None:
    path = write_events_csv(
        tmp_path,
        "timestamp,severity,code,message\n"
        "2026-07-13T23:00:00+00:00,info,A,before window\n"
        "2026-07-14T00:00:00+00:00,info,B,on start boundary\n"
        "2026-07-14T12:00:00+00:00,info,C,inside\n"
        "2026-07-15T00:00:00+00:00,info,D,after window\n",
    )

    events = read_events_csv(path, START, END)

    assert [event.code for event in events] == ["B", "C"]


def test_read_events_csv_empty_file(tmp_path: Path) -> None:
    path = write_events_csv(tmp_path, "")

    with pytest.raises(ValueError, match="is empty"):
        read_events_csv(path, START, END)


def test_read_events_csv_header_only_returns_no_events(tmp_path: Path) -> None:
    path = write_events_csv(tmp_path, "timestamp,severity,code,message\n")

    assert read_events_csv(path, START, END) == []
