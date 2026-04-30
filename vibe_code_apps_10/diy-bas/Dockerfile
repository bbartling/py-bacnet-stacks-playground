FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=5050

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY bas ./bas
COPY diybas ./diybas
COPY frontend ./frontend
COPY manage.py ./manage.py
COPY docker-entrypoint.sh ./docker-entrypoint.sh

RUN sed -i 's/\r$//' /app/docker-entrypoint.sh \
    && chmod +x /app/docker-entrypoint.sh \
    && python manage.py collectstatic --noinput

EXPOSE 5050
VOLUME ["/app/data"]

ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]
