# Running solar-report with Docker

The fastest way to try the project: no local Python install, just Docker.

## 1. Prerequisites

- Docker
- Docker Compose (bundled with Docker Desktop; on Linux it's the `docker compose` plugin)

## 2. Configure

```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

Open `.env` and set `ANTHROPIC_API_KEY` to your Anthropic key.

`config.yaml` uses the bundled sample dataset in `sample-data/` by default —
fine for a first try. To use your own data, see step 4.

## 3. Run

```bash
docker compose up --build
```

The report is generated and written to `./reports/` on the host machine
(the folder is mounted as a volume, not left only inside the container).

## 4. Use your own data

Edit `config.yaml`:

- `source.csv.path`: point it at your own CSV file (format described in
  [`docs/csv-format.md`](./csv-format.md))
- `report.period`: `week` or `month`

The Home Assistant source is not available yet in v0.1 (see the roadmap in
`CLAUDE.md`); for now CSV is the only supported source.

If you only change `config.yaml` or the files in `sample-data/`, no rebuild
is needed: they're mounted as bind mounts. A rebuild is only required when
dependencies or the source code change:

```bash
docker compose build --no-cache
```

## 5. One-off run vs. recurring

The command generates a single report and the container exits — this is not
a long-running service. To regenerate, re-run `docker compose up`. For a
recurring schedule (e.g. every Monday), use `cron` on the host to call
`docker compose run --rm solar-report`, or an external job scheduler; this
is not bundled with the project.

## Troubleshooting

**`environment variable 'ANTHROPIC_API_KEY' referenced in config is not set`**
`.env` is missing or empty. Make sure it exists at the project root and
contains the key.

**`./reports/` stays empty after `docker compose up`**
Check the container logs:

```bash
docker compose logs
```

Common causes: CSV not found (wrong path in `config.yaml`) or missing
columns in the CSV (see `docs/csv-format.md`).

**Changes to the CSV have no effect**
If the container was already running, the bind mount is still read
synchronously: make sure you saved the file and re-ran `docker compose up`
(the command runs once, there's no watcher).
