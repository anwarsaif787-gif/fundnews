from datetime import datetime, timezone
from time import mktime

import feedparser
from django.core.management.base import BaseCommand
from news.models import Source
from news.services import FEED_AGENT


class Command(BaseCommand):
    help = "Test every news feed: does it load, how many items, how recent"

    def handle(self, *args, **kwargs):
        now = datetime.now(timezone.utc)
        good, bad = 0, 0
        for s in Source.objects.order_by('name'):
            try:
                feed = feedparser.parse(s.feed_url, agent=FEED_AGENT)
            except Exception as exc:  # network trouble must not stop the check
                self.stdout.write(f"BROKEN  {s.name}: {exc}")
                bad += 1
                continue
            status = getattr(feed, 'status', None)
            n = len(feed.entries)
            newest = None
            for e in feed.entries:
                t = e.get('published_parsed') or e.get('updated_parsed')
                if t:
                    d = datetime.fromtimestamp(mktime(t), tz=timezone.utc)
                    if newest is None or d > newest:
                        newest = d
            if n == 0:
                why = f"HTTP {status}" if status else "could not connect"
                self.stdout.write(f"BROKEN  {s.name}: no items ({why})")
                bad += 1
            elif newest and (now - newest).days > 30:
                self.stdout.write(f"STALE   {s.name}: {n} items, newest {newest:%d %b %Y}")
                bad += 1
            else:
                when = f"newest {newest:%d %b %Y}" if newest else "no dates"
                self.stdout.write(f"OK      {s.name}: {n} items, {when}")
                good += 1
        self.stdout.write(f"\n{good} working, {bad} need attention. "
                          "Remove broken or stale ones in the editor at /admin under Sources.")
