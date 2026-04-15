FROM python:3.12-slim-bookworm

WORKDIR /app

RUN pip install --no-cache-dir "easy-aso[platform]==0.1.5" httpx

COPY run_oat_share.py /app/run_oat_share.py

ENV OAT_INTERVAL_SEC=300 \
    SUPERVISOR_BACNET_RPC_URL=http://diy-bacnet:8080 \
    SUPERVISOR_BACNET_RPC_ENTRYPOINT=/api

CMD ["python", "-u", "/app/run_oat_share.py"]
