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

# System build deps for rasterio/GDAL, shapely/GEOS, pyproj/PROJ
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libgdal-dev \
    gdal-bin \
    libgeos-dev \
    libproj-dev \
    && rm -rf /var/lib/apt/lists/*

ENV GDAL_VERSION=3.6

WORKDIR /build

# Install build tooling first (better layer caching)
RUN pip install --upgrade pip setuptools wheel

# Copy only manifests to leverage Docker layer caching
COPY pyproject.toml README.md ./
COPY wildfire_front/ wildfire_front/
COPY models/ models/

# Wheel package + all install_requires (numpy, rasterio, affine, shapely, pyproj
# and their transitive deps) so runtime --no-index install succeeds.
RUN pip wheel . -w /wheels

# ─── Stage 2: Runtime ───────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="WildfireFrontDynamics" \
      org.opencontainers.image.description="Wildfire front reconstruction from thermal imagery" \
      org.opencontainers.image.source="https://github.com/AlonsoAlviraa/WildfireFrontDynamics" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Runtime system libs: GDAL + GEOS + PROJ (no -dev) + curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal32 \
    gdal-bin \
    libgeos-c1v5 \
    libproj25 \
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

# Import geospatial stack + package (validates wheels + system libs)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import shapely, pyproj, rasterio, wildfire_front; print('healthy')" || exit 1

ENTRYPOINT ["python", "-m", "wildfire_front"]
CMD ["--help"]

# ─── Stage 3: NDWS spread inference (v21 production) ───────────────────────
# .pt weights are gitignored. CI builds this stage with manifests only.
# For real inference, either:
#   - place weights under models/production/ before `docker build`, or
#   - bind-mount them at runtime, e.g.:
#       docker run --rm \
#         -v /path/to/weights_v21_best.pt:/app/models/production/weights_v21_best.pt:ro \
#         -v /path/to/spread_model_v21.pt:/app/models/production/spread_model_v21.pt:ro \
#         wildfire-front-dynamics:inference ...
FROM runtime AS inference

USER root

# CPU-only PyTorch for slim inference image
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY --chown=wfapp:wfapp models/production/ /app/models/production/

ENV WILDFIRE_MANIFEST=/app/models/production/manifest.json \
    WILDFIRE_TORCHSCRIPT=/app/models/production/spread_model_v21.pt \
    PYTHONPATH=/app

USER wfapp

# Import-only healthcheck (does not require .pt on disk)
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import torch; import wildfire_front.ml.spread_predictor as s; print('inference-ok')" || exit 1

ENTRYPOINT ["python", "/app/scripts/predict_spread.py"]
CMD ["--help"]