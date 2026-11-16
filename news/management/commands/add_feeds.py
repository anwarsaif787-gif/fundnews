from django.core.management.base import BaseCommand
from news.models import Source

# Direct feeds, taken from the rss.feedspot.com directory of private equity feeds.
# They have not been tested: run "python manage.py check_feeds" to see which work.
DIRECT = [
    ('Private Equity International', 'https://www.privateequityinternational.com/feed/'),
    ('AltAssets', 'https://www.altassets.net/feed'),
    ('Private Equity Wire', 'https://www.privateequitywire.co.uk/dailynews.xml'),
    ('Unquote', 'https://www.unquote.com/feeds/rss'),
    ('Private Equity News', 'https://www.penews.com/rss/?x=1'),
    ('DailyAlts', 'https://dailyalts.com/feed/'),
    ('TechCrunch Private Equity', 'https://techcrunch.com/tag/private-equity/feed/'),
    ('Growth Business VC Funding', 'https://growthbusiness.co.uk/funding/venture-capital-funding/feed/'),
]

# Sites with no feed address we could find. Google News can list their recent
# headlines instead (last 7 days only).
SITE_SEARCH = [
    ('PE Hub', 'pehub.com'),
    ('Private Equity Real Estate', 'perenews.com'),
    ('Buyouts', 'buyoutsinsider.com'),
    ('Institutional Investor', 'institutionalinvestor.com'),
    ('Infrastructure Investor', 'infrastructureinvestor.com'),
    ('Real Deals', 'realdeals.eu.com'),
    ('Alternative Credit Investor', 'alternativecreditinvestor.com'),
    ('FinSMEs', 'finsmes.com'),
    ('AVCJ', 'avcj.com'),
    ('Inc42', 'inc42.com'),
    ('Entrackr', 'entrackr.com'),
    ('VCCircle', 'vccircle.com'),
    ('YourStory', 'yourstory.com'),
]


class Command(BaseCommand):
    help = "Add specialist publication feeds (safe to run again)"

    def handle(self, *args, **kwargs):
        added = 0
        for name, url in DIRECT:
            _, new = Source.objects.get_or_create(feed_url=url, defaults={'name': name})
            added += new
        for name, domain in SITE_SEARCH:
            url = f'https://news.google.com/rss/search?q=site:{domain}+when:7d'
            _, new = Source.objects.get_or_create(feed_url=url, defaults={'name': f'{name} (via Google News)'})
            added += new
        self.stdout.write(f"Added {added} feeds. Now run: python manage.py check_feeds")
