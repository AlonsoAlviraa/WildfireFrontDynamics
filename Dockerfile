# WildfireFrontDynamics - Multi-stage Dockerfile
# Produces a slim runtime image for inference and batch processing
#
# Build:
#   docker build -t wildfire-front-dynamics:0.1.0 .
# Run:
#   docker run --rm wildfire-front-dynamics:0.1.0 wildfire-front --help
# Dev shell:
#   docker run --rm -it wildfire-front-dynamics:0.1.0 bash

# ─── Stage 1: Builder ───────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System build deps for rasterio/GDAL
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libgdal-dev \
    gdal-bin \
    && rm -rf /var/lib/apt/lists/*

ENV GDAL_VERSION=3.6

WORKDIR /build

# Install build tooling first (better layer caching)
RUN pip install --upgrade pip setuptools wheel

# Copy only manifests to leverage Docker layer caching
COPY pyproject.toml README.md ./
COPY wildfire_front/ wildfire_front/

# Build wheel
RUN pip wheel . --no-deps -w /wheels && \
    pip wheel numpy rasterio affine -w /wheels

# ─── Stage 2: Runtime ───────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="WildfireFrontDynamics" \
      org.opencontainers.image.description="Wildfire front reconstruction from thermal imagery" \
      org.opencontainers.image.source="https://github.com/AlonsoAlviraa/WildfireFrontDynamics" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Runtime system deps: GDAL libs (no -dev) + curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal32 \
    gdal-bin \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN groupadd -r wfapp && useradd -r -g wfapp -d /app -s /sbin/nologin wfapp

WORKDIR /app

# Copy pre-built wheels from builder
COPY --from=builder /wheels /wheels

# Install from wheels (no build tools needed)
RUN pip install --no-index --find-links=/wheels wildfire-front-dynamics && \
    rm -rf /wheels

# Copy models package and scripts for batch processing
COPY --chown=wfapp:wfapp models/ /app/models/
COPY --chown=wfapp:wfapp scripts/ /app/scripts/

USER wfapp

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import wildfire_front; print('healthy')" || exit 1

ENTRYPOINT ["python", "-m", "wildfire_front"]
CMD ["--help"]