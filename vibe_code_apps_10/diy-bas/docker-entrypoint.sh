#!/bin/sh
set -e
cd /app
python manage.py migrate --noinput
exec gunicorn diybas.wsgi:application --bind "0.0.0.0:${PORT:-5050}" --workers 2 --threads 4 --timeout 120
