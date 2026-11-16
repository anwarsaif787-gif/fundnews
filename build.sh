#!/usr/bin/env bash
# Runs once each time the site is built online.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
python manage.py setup_defaults
python manage.py add_feeds

# Create the editor login from the settings you typed in Render (skipped if it exists).
python manage.py createsuperuser --no-input || true

# First batch of stories (does not stop the build if a feed is down).
python manage.py fetch_news || true
python manage.py organize || true
