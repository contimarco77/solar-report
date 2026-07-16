"""Protocol shared by all production-data sources."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from solar_report.analysis.models import ProductionData


@runtime_checkable
class DataSource(Protocol):
    """A source of PV production time-series data.

    Contract for implementations:

    - ``start`` and ``end`` must be timezone-aware datetimes; naive values
      are rejected with :class:`ValueError`.
    - The window is inclusive on both ends: a point is returned when
      ``start <= point.timestamp <= end``.
    - Returned points are sorted by timestamp, ascending.
    - Unreadable or malformed data raises :class:`ValueError` with a message
      that identifies the offending input (file, row, entity, ...).
    """

    def read(self, start: datetime, end: datetime) -> list[ProductionData]:
        """Return production points within the inclusive ``[start, end]`` window."""
        ...
