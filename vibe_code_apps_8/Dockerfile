FROM python:3.10-slim-bookworm AS volttron-runtime

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
        libffi-dev \
        libssl-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash volttron

ENV VOLTTRON_VENV=/home/volttron/env
ENV PATH=/home/volttron/env/bin:$PATH

WORKDIR /home/volttron

# VOLTTRON 10.x requires legacy pip; keep setuptools conservative for pkg_resources + vctl.
RUN python -m venv "${VOLTTRON_VENV}" \
    && pip install --no-cache-dir --upgrade "pip==22.2.2" "wheel" "setuptools==65.5.1" \
    && pip install --no-cache-dir \
        "volttron==10.0.5rc4" \
        "volttron-lib-web==0.2.0rc0" \
        "werkzeug<3" \
    # Pin zope stack for gevent/pkg_resources; zope.interface 5.5.2 must not upgrade setuptools (82 drops pkg_resources layout vctl needs).
    && pip install --no-cache-dir --force-reinstall \
        "setuptools==65.5.1" \
        "zope.interface==5.5.2" \
        "zope.event==4.6" \
    && chown -R volttron:volttron /home/volttron/env \
    && python -c "import site, pkg_resources; site.main(); pkg_resources.require('zope.interface'); print('pkg_resources: zope.interface ok')"

WORKDIR /workspace

# Entrypoint fixes named-volume ownership then re-execs as volttron (see start-volttron.sh).
USER root
