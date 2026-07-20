# syntax=docker/dockerfile:1
#
# Multi-stage image: the "builder" stage installs the build tools required by
# some dependencies (e.g. pandas) and creates a venv; the "runtime" stage
# copies only the resulting venv, without the build toolchain, for a smaller
# final image with a reduced attack surface.

FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir .


FROM python:3.11-slim AS runtime

# Non-root user: the image does not need elevated privileges.
RUN useradd --create-home --uid 1000 solar
WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Sample data and reference config, so the image works out of the box even
# without a bind mount (quick demo/trial).
COPY --chown=solar:solar sample-data ./sample-data
COPY --chown=solar:solar config.example.yaml ./config.example.yaml

USER solar

ENTRYPOINT ["solar-report"]
CMD ["generate", "--config", "config.yaml", "--period", "week"]
