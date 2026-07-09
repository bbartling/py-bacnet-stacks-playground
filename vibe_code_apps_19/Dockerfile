# Open FDD Vibe Coder — Docker image (analyst + deploy modes)
#
# Build from repo root:
#   docker build -f vibe_code_apps_19/Dockerfile -t open-fdd-vibe-coder vibe_code_apps_19
#
# Analyst mode (live tune + refresh; mount HVAC CSV tree):
#   docker run --rm -p 5000:5000 \
#     -v /path/to/hvac_systems_CLEANED:/data/hvac \
#     -e HVAC_DATA_ROOT=/data/hvac \
#     -e DASHBOARD_MODE=full \
#     open-fdd-vibe-coder
#
# Deploy mode (pre-baked site/ only — build site/ first with package_dashboard.py):
#   docker run --rm -p 5000:5000 \
#     -e DASHBOARD_MODE=deploy \
#     open-fdd-vibe-coder:deploy

FROM python:3.12-slim

WORKDIR /app

COPY shared/ shared/
COPY haystack_rdf/ haystack_rdf/
COPY fdd_app/ fdd_app/

RUN pip install --no-cache-dir -r fdd_app/requirements-dev.txt \
    && pip install --no-cache-dir gunicorn

WORKDIR /app/fdd_app

ENV PYTHONUNBUFFERED=1
ENV DASHBOARD_MODE=full
ENV ANALYST_ENABLED=1
ENV HVAC_DATA_ROOT=/data/hvac

EXPOSE 5000

# Uvicorn worker under Gunicorn for production; override with `python app.py` for local-style dev
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:5000", "--timeout", "300", "asgi:app"]
