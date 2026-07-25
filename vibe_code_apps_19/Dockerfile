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

# Chrome/Chromium shared libs required by Kaleido ≥1 (Plotly PNG export → DOCX).
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      fonts-liberation \
      libasound2 \
      libatk-bridge2.0-0 \
      libatk1.0-0 \
      libcups2 \
      libdbus-1-3 \
      libdrm2 \
      libgbm1 \
      libgtk-3-0 \
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
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && python -c "import kaleido; kaleido.get_chrome_sync()" \
 && python -c "import docx, kaleido, matplotlib; print('engineering-report extras ok')" \
 && python -c "import plotly.graph_objects as go; from pathlib import Path; p=Path('/tmp/kaleido_smoke.png'); fig=go.Figure(data=[go.Bar(x=['a'], y=[1])]); fig.write_image(str(p)); assert p.is_file() and p.stat().st_size>100; print('kaleido png ok', p.stat().st_size)"

# Includes .streamlit/config.toml (maxUploadSize=500) — do not lower OPENFDD_MAX_* here.
COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
