#!/usr/bin/env bash
# Runs once each time the site is built online.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
python manage.py setup_defaults
python manage.py add_feeds

# Create or reset the editor login from the username and password set in Render.
python manage.py shell -c "
import os
from django.contrib.auth import get_user_model
User = get_user_model()
user, _ = User.objects.get_or_create(username=os.environ['DJANGO_SUPERUSER_USERNAME'].strip())
user.is_staff = True
user.is_superuser = True
user.set_password(os.environ['DJANGO_SUPERUSER_PASSWORD'].strip())
user.save()
print('Editor login ready:', user.username)
"

# First batch of stories (does not stop the build if a feed is down).
python manage.py fetch_news || true
# Regroup all stories with the latest rules (articles are kept).
python manage.py organize --reset || true
