#!/bin/sh
set -e

export FLASK_APP=wsgi:app

exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 60 wsgi:app
