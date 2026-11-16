import feedparser
from datetime import datetime, timezone
from time import mktime
from django.core.management.base import BaseCommand
from news.models import Source, Category, Article
from news.services import FEED_AGENT, is_noise, keyword_match, load_context, process_article, tidy


class Command(BaseCommand):
    help = "Fetch new articles from all sources and group them into stories"

    def handle(self, *args, **kwargs):
        ctx = load_context()
        added = 0

        for source in Source.objects.all():
            feed = feedparser.parse(source.feed_url, agent=FEED_AGENT)
            self.stdout.write(f"{source.name}: {len(feed.entries)} items found")

            for e in feed.entries:
                link = e.get("link")
                title = e.get("title")
                if not link or not title:
                    continue
                if is_noise(title) or Article.objects.filter(link=link).exists():
                    continue

                text = tidy(title, source.name)[0].lower()
                category = next((c for c in ctx['categories']
                                 if keyword_match(text, c.keywords)), None)

                t = e.get("published_parsed")
                published = (
                    datetime.fromtimestamp(mktime(t), tz=timezone.utc)
                    if t else datetime.now(timezone.utc)
                )

                article = Article.objects.create(
                    source=source,
                    category=category,
                    title=title[:300],
                    link=link[:1000],
                    summary=e.get("summary", "")[:1000],
                    published=published,
                )
                process_article(article, ctx)
                added += 1

        self.stdout.write(f"Done. Added {added} new articles.")
