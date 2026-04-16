# Clone bbartling/diy-bacnet-server default branch (shallow). Compose git URLs are unreliable on Windows.
# To pin a revision, replace this RUN with a COPY from a vendored checkout or add a git checkout of a tag/SHA.

# diy-bacnet-server master requires-python >=3.14 (see upstream pyproject.toml).
FROM python:3.14-slim-bookworm

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

# Upstream may ship requirements.txt (older) or pyproject.toml only (current master).
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && if [ -f /app/requirements.txt ]; then \
         pip install --no-cache-dir -r /app/requirements.txt; \
       elif [ -f /app/pyproject.toml ]; then \
         pip install --no-cache-dir "/app"; \
       else \
         echo "diy-bacnet-server: no requirements.txt or pyproject.toml under /app" >&2; ls -la /app; exit 1; \
       fi

EXPOSE 47808/udp
EXPOSE 8080

CMD ["python3", "-u", "-m", "bacpypes_server.main", "--name", "BensServer", "--instance", "123456", "--public"]
