# CSV format

The CSV source reads PV production data from a file with a header row and at
least these two columns (extra columns are ignored):

| Column          | Type   | Description                                                        |
| --------------- | ------ | ------------------------------------------------------------------ |
| `timestamp`     | string | ISO 8601 with an **explicit timezone offset** (`+02:00`, `Z`, ...) |
| `production_wh` | float  | Energy produced in the interval, in watt-hours. Must be ≥ 0.      |

Naive timestamps (without offset) are rejected: DST transitions and exports
from systems in different timezones would otherwise be ambiguous.

> **Incremental, not cumulative.** The `production_wh` column contains the
> incremental energy for the interval ending at `timestamp`, not a cumulative
> meter reading. Daily totals are computed by *summing* rows, so a cumulative
> counter (e.g. a meter reading that grows during the day, as in Solar-Log
> daily exports or Home Assistant `total_increasing` sensors) would inflate
> the totals by the number of readings. Convert cumulative readings to
> per-interval differences before importing.

## Example

```csv
timestamp,production_wh
2026-07-14T10:00:00+02:00,1250.5
2026-07-14T11:00:00+02:00,1810.0
2026-07-14T12:00:00+02:00,2005.25
```

## European exports (semicolon + comma decimal)

Many European tools export CSV with `;` as separator and `,` as decimal mark:

```csv
timestamp;production_wh
2026-07-14T10:00:00+02:00;1250,5
2026-07-14T11:00:00+02:00;1810,0
```

Both are configurable in `config.yaml` — the defaults are `,` and `.`:

```yaml
source:
  kind: "csv"
  csv:
    path: "./data/production.csv"
    separator: ";"
    decimal: ","
```

and in code via `CsvDataSource(path, separator=";", decimal=",")`.

## Errors you may see

- *"CSV file ... is empty"* — the file has no content at all.
- *"missing required columns"* — check the header row (and the separator: a
  European file read with the default `,` separator looks like one big column).
- *"timestamp ... has no timezone"* — add the UTC offset to your timestamps.
- *"production_wh ... is not a number"* — usually a separator/decimal mismatch.
