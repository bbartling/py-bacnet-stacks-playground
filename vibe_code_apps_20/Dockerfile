# WattLab Studio container — ESCO / capital-planning cockpit.
# Serves studio.py (Streamlit). EnergyPlus runs need a Docker daemon, which is
# not available inside this container — the Studio dry-run / benchmark /
# measures / capital-plan paths are fully functional; run real E+ simulations
# from a host checkout (`wattlab easy-button`) instead.
FROM python:3.12-slim

ARG VIBE20_GIT_SHA=unknown
ARG VIBE20_IMAGE_REF=ghcr.io/bbartling/vibe20
ARG VIBE20_IMAGE_TAG=local

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIBE20_DOCKER=1 \
    WATTLAB_ROOT=/app \
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
