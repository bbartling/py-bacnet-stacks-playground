# WattLab Studio container — ESCO / capital-planning cockpit (Streamlit).
#
# EnergyPlus: mount the host Docker socket + set WATTLAB_HOST_WORKSPACE to the
# host path of the /data bind so Twin → Run EnergyPlus (Docker) can spawn
# energyplus-mcp-dev (DinD). Artifacts under /data/.artifacts; sibling stage
# mounts + world-writable out dirs + --user 1000:1000 for ReadVars CSV.
# Without docker.sock, dry-run / Fuel / ECMs still work; agents can publish
# runs/ from a host checkout (`wattlab easy-button`).
#
# Entry point: studio.py (not wattlab/studio/app.py).
FROM python:3.12-slim

ARG VIBE20_GIT_SHA=unknown
ARG VIBE20_IMAGE_REF=ghcr.io/bbartling/vibe20
ARG VIBE20_IMAGE_TAG=local

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIBE20_DOCKER=1 \
    WATTLAB_ROOT=/app \
    ENERGYPLUS_DOCKER_USER=1000:1000 \
    VIBE20_GIT_SHA=${VIBE20_GIT_SHA} \
    VIBE20_IMAGE_REF=${VIBE20_IMAGE_REF} \
    VIBE20_IMAGE_TAG=${VIBE20_IMAGE_TAG} \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

LABEL org.opencontainers.image.title="vibe20" \
      org.opencontainers.image.description="OpenFDD WattLab Studio — EnergyPlus twin + ESCO capital planning" \
      org.opencontainers.image.source="https://github.com/bbartling/py-bacnet-stacks-playground" \
      org.opencontainers.image.revision="${VIBE20_GIT_SHA}" \
      org.opencontainers.image.ref.name="${VIBE20_IMAGE_REF}:${VIBE20_IMAGE_TAG}"

WORKDIR /app

COPY . .
RUN pip install --no-cache-dir ".[studio]"

EXPOSE 8501

CMD ["streamlit", "run", "studio.py", "--server.port=8501", "--server.address=0.0.0.0"]
