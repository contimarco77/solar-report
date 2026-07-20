# Events format

The events source is optional and separate from the production CSV (see
[csv-format.md](csv-format.md)). It adds vendor-reported alarms and
operational events to the report, so Observations and Recommendations can
reference a concrete cause instead of only a hedged guess. If it is not
configured, the tool behaves exactly as without it.

The file must have a header row with these four columns:

| Column      | Type   | Description                                                  |
| ----------- | ------ | -------------------------------------------------------------- |
| `timestamp` | string | ISO 8601 with an **explicit timezone offset** (`+02:00`, `Z`, ...) |
| `severity`  | string | One of `info`, `warning`, `critical` (exact match, case-sensitive) |
| `code`      | string | Free-form vendor/error code                                    |
| `message`   | string | Free-form human-readable description                          |

Naive timestamps (without offset) are rejected, for the same reason as in the
production CSV: DST transitions and multi-timezone exports would otherwise be
ambiguous.

> **Severity is a closed set.** Vendors expose their own severity scales
> (numeric levels, vendor-specific labels, ...). If you are exporting from a
> system with a different scale, map it onto `info` / `warning` / `critical`
> before writing the CSV — the column is validated strictly and any other
> value is rejected.

## Example

```csv
timestamp,severity,code,message
2026-07-08T14:30:00+02:00,warning,INV-042,Inverter derating detected
2026-07-15T09:12:00+02:00,info,SYS-001,Scheduled maintenance check
```

## Configuration

```yaml
source:
  kind: "csv"
  csv:
    path: "./data/production.csv"
    events_path: "./data/events.csv"
```

`events_path` is optional. Omit it (or leave it unset) to run without an
events source.

## How events reach the report

Events are not handed to the LLM as-is. For each event, the tool checks in
code whether its date matches a day already flagged in anomaly detection, and
marks it explicitly (`[matches anomaly day]`) before it is included in the
prompt. The model is instructed to mention an event in Observations or
Recommendations only when it carries that marker — it never infers the
correlation itself. Events with no marker, or an empty events list, are not
mentioned in the generated report at all.

## Errors you may see

- *"CSV file ... is empty"* — the file has no content at all.
- *"missing required columns"* — check the header row: all four columns
  (`timestamp`, `severity`, `code`, `message`) are required.
- *"timestamp ... has no timezone"* — add the UTC offset to your timestamps.
- A `severity` value outside `info` / `warning` / `critical` fails validation
  — map your vendor's scale onto these three levels first.
