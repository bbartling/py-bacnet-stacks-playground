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
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    # Kaleido/choreographer: distro Chromium (native amd64+arm64; avoid chrome-linux64 under QEMU)
    BROWSER_PATH=/usr/bin/chromium

LABEL org.opencontainers.image.title="vibe19" \
      org.opencontainers.image.description="OpenFDD Vibe 19 Streamlit FDD demo" \
      org.opencontainers.image.source="https://github.com/bbartling/py-bacnet-stacks-playground" \
      org.opencontainers.image.revision="${VIBE19_GIT_SHA}" \
      org.opencontainers.image.ref.name="${VIBE19_IMAGE_REF}:${VIBE19_IMAGE_TAG}"

WORKDIR /app

# Chromium + shared libs for Kaleido ≥1 Plotly→PNG (DOCX Overview charts).
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      chromium \
      fonts-liberation \
      libasound2t64 \
      libatk-bridge2.0-0t64 \
      libatk1.0-0t64 \
      libcups2t64 \
      libdbus-1-3 \
      libdrm2 \
      libgbm1 \
      libgtk-3-0t64 \
      libnspr4 \
      libnss3 \
      libpango-1.0-0 \
      libx11-xcb1 \
      libxcomposite1 \
      libxdamage1 \
      libxfixes3 \
      libxkbcommon0 \
      libxrandr2 \
      xdg-utils \
    && rm -rf /var/lib/apt/lists/* \
    && test -x /usr/bin/chromium \
    && /usr/bin/chromium --version

COPY requirements.txt ./
COPY scripts/docker_kaleido_smoke.py /tmp/docker_kaleido_smoke.py
RUN pip install --no-cache-dir -r requirements.txt \
 && python -c "import docx, kaleido, matplotlib; print('engineering-report extras ok')" \
 && python /tmp/docker_kaleido_smoke.py

# In-container test runner (BUG-041): pytest is not a runtime/cloud dependency,
# so it stays out of requirements.txt and is installed Docker-only. Lets
# AppTests run ``python -m pytest`` inside the GHCR image.
RUN pip install --no-cache-dir "pytest>=8"

# Includes .streamlit/config.toml (maxUploadSize=500) — do not lower OPENFDD_MAX_* here.
COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
