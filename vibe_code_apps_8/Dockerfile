# BAS Lite supervisor (Flask + static vannila UI). Pair with diy-bacnet-server on the same host network.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV SUPERVISOR_WEBROOT=/app/vannila
ENV SUPERVISOR_DATA_DIR=/data
# Default matches diy-bacnet-server Docker image (HTTP on 5000 per upstream Dockerfile).
ENV DIY_BACNET_URL=http://127.0.0.1:5000
ENV PORT=5050
ENV BIND=0.0.0.0

WORKDIR /app/supervisor_flask

COPY supervisor_flask/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY supervisor_flask/ ./
COPY vannila/ /app/vannila/

RUN mkdir -p /data

EXPOSE 5050
VOLUME ["/data"]

CMD ["python", "app.py"]
