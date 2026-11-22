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
python manage.py fill_summaries --limit 40 || true

# Add upcoming private markets events (safe to repeat; nothing is duplicated).
python manage.py shell <<'PY' || true
from datetime import date
from news.models import Event
PEI = "PEI Group"
events = [
    ("SuperReturn North America 2027", date(2027, 2, 1), date(2027, 2, 3), "Hollywood, Florida", "Informa Connect", "https://informaconnect.com/superreturn-north-america/"),
    ("Private Fund Compliance Operations Forum 2026", date(2026, 12, 1), date(2026, 12, 2), "New York", PEI, "https://www.peievents.com/en/event/private-fund-compliance-operations-forum/"),
    ("Women in Private Markets Summit 2026", date(2026, 12, 2), date(2026, 12, 3), "London", PEI, "https://www.peievents.com/en/event/women-in-private-markets-summit/"),
    ("Private Funds CFO New York Forum 2027", date(2027, 1, 26), date(2027, 1, 27), "New York City", PEI, "https://www.peievents.com/en/event/cfo-new-york/"),
    ("Infrastructure Investor Global Summit 2027", date(2027, 2, 22), date(2027, 2, 25), "Berlin", PEI, "https://www.peievents.com/en/event/infrastructure-investor-global-summit/"),
    ("PERE Asia Summit 2027", date(2027, 3, 1), date(2027, 3, 3), "Singapore", PEI, "https://www.peievents.com/en/event/pere-asia/"),
    ("NEXUS 2027", date(2027, 3, 1), date(2027, 3, 4), "Scottsdale, Arizona", PEI, "https://www.peievents.com/en/event/pei-nexus/"),
    ("Responsible Investment Forum: New York 2027", date(2027, 3, 9), date(2027, 3, 10), "New York", PEI, "https://www.peievents.com/en/event/responsible-investment-forum-new-york/"),
    ("Operating Partners Human Capital Forum 2027", date(2027, 4, 6), date(2027, 4, 8), "New York", PEI, "https://www.peievents.com/en/event/operating-partners-human-capital-forum/"),
    ("PEI Private Credit Japan Korea Week 2027", date(2027, 4, 20), date(2027, 4, 23), "Seoul and Tokyo", PEI, "https://www.peievents.com/en/event/pdi-japan-korea-week/"),
    ("PEI Private Credit New York Forum 2027", date(2027, 5, 18), date(2027, 5, 19), "New York", PEI, "https://www.peievents.com/en/event/pdi-new-york-forum/"),
    ("Impact Investor Global Summit 2027", date(2027, 5, 18), date(2027, 5, 19), "London", PEI, "https://www.peievents.com/en/event/impact-investor-global-summit/"),
]
added = 0
for title, start, end, city, org, url in events:
    _, new = Event.objects.get_or_create(
        title=title, start_date=start,
        defaults=dict(end_date=end, city=city, organizer=org, url=url, is_webinar=False))
    added += new
print("Events added:", added)
PY
