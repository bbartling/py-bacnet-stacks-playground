# Self-host / local parity only — Streamlit Community Cloud does NOT use this file.
# Cloud: Main file = streamlit_app.py + requirements.txt (see docs/STREAMLIT_CLOUD.md).
FROM python:3.12-slim

# Baked at GHCR build time so `docker inspect` / Streamlit sidebar show a real image name
# (not only a short content hash like caab217c7f84).
ARG VIBE19_GIT_SHA=unknown
ARG VIBE19_IMAGE_REF=ghcr.io/bbartling/vibe19
ARG VIBE19_IMAGE_TAG=local

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_MODE=cloud \
    VIBE19_DOCKER=1 \
    VIBE19_GIT_SHA=${VIBE19_GIT_SHA} \
    VIBE19_IMAGE_REF=${VIBE19_IMAGE_REF} \
    VIBE19_IMAGE_TAG=${VIBE19_IMAGE_TAG} \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

LABEL org.opencontainers.image.title="vibe19" \
      org.opencontainers.image.description="OpenFDD Vibe 19 Streamlit FDD demo" \
      org.opencontainers.image.source="https://github.com/bbartling/py-bacnet-stacks-playground" \
      org.opencontainers.image.revision="${VIBE19_GIT_SHA}" \
      org.opencontainers.image.ref.name="${VIBE19_IMAGE_REF}:${VIBE19_IMAGE_TAG}"

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && python -c "import docx, kaleido, matplotlib; print('engineering-report extras ok')"

# Includes .streamlit/config.toml (maxUploadSize=500) — do not lower OPENFDD_MAX_* here.
COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
