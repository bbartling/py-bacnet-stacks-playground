FROM python:3.12-slim-bookworm

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY bas_lite_api ./bas_lite_api
# PyPI may lag; install easy-aso from Git so JsonRpc Bearer (0.1.5+) is available. Remove this line once PyPI has easy-aso>=0.1.5.
ARG EASY_ASO_GIT_REF=master
RUN pip install --no-cache-dir pip setuptools wheel \
    && pip install --no-cache-dir "easy-aso[platform] @ git+https://github.com/bbartling/easy-aso.git@${EASY_ASO_GIT_REF}" \
    && pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1
ENV SUPERVISOR_DB_PATH=/data/supervisor.sqlite

EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -sf http://127.0.0.1:8090/api/v1/health || exit 1
CMD ["uvicorn", "bas_lite_api.main:app", "--host", "0.0.0.0", "--port", "8090", "--proxy-headers"]
