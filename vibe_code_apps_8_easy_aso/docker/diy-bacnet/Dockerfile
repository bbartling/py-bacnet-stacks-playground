# Clone bbartling/diy-bacnet-server default branch (shallow). Compose git URLs are unreliable on Windows.
# To pin a revision, replace this RUN with a COPY from a vendored checkout or add a git checkout of a tag/SHA.

FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    iproute2 \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/bbartling/diy-bacnet-server.git /tmp/diy \
    && cp -a /tmp/diy/. /app/ \
    && rm -rf /tmp/diy

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

EXPOSE 47808/udp
EXPOSE 8080

CMD ["python3", "-u", "-m", "bacpypes_server.main", "--name", "BensServer", "--instance", "123456", "--public"]
