FROM python:3.12-slim-bookworm

WORKDIR /app
# curl: healthcheck. build-essential: armv7l often has no binary wheels for psutil / httptools / uvloop → pip compiles from source.
# (Official image already ships /usr/local/include/python3.12 — avoid Debian python3-dev mismatch.)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY bas_lite_api ./bas_lite_api
RUN pip install --no-cache-dir pip setuptools wheel \
    && pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1
ENV SUPERVISOR_DB_PATH=/data/supervisor.sqlite

EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -sf http://127.0.0.1:8090/api/v1/health || exit 1
CMD ["uvicorn", "bas_lite_api.main:app", "--host", "0.0.0.0", "--port", "8090", "--proxy-headers"]
