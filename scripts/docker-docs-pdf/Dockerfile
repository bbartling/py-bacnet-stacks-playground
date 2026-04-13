# Image for building Markdown → PDF (Pandoc + WeasyPrint). Mount repo at /work.
FROM python:3.12-slim-bookworm

RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends \
        pandoc \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libffi-dev \
        shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pyyaml weasyprint

WORKDIR /work
