FROM python:3.12-slim-bookworm

WORKDIR /app

RUN pip install --no-cache-dir "easy-aso[platform]==0.1.7" httpx

COPY agents /app/agents

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    SUPERVISOR_BACNET_RPC_URL=http://diy-bacnet:8080 \
    SUPERVISOR_BACNET_RPC_ENTRYPOINT=/api \
    EASY_ASO_AGENT_MODULE=easy_aso.runtime.sample_agent \
    EASY_ASO_AGENT_CLASS=SampleAgent \
    EASY_ASO_STEP_SEC=30

CMD ["easy-aso-agent", "run"]
