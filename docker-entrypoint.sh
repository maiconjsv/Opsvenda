#!/bin/sh
set -e

export FLASK_APP=wsgi:app

# Applied once here, before the workers start, instead of inside each
# Gunicorn worker (which would race on the same schema change).
flask db upgrade

exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 60 wsgi:app
