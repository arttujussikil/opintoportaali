#!/bin/sh
set -e

echo "Running database setup..."
python database2.py

echo "Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:8080 --workers 2 --timeout 60 app:app
