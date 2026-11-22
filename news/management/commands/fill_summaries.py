from concurrent.futures import ThreadPoolExecutor

from django.core.management.base import BaseCommand

from news.models import Article
from news.summaries import fetch_description
from news.views import clean_summary


class Command(BaseCommand):
    help = "Fetch a short description from the publisher's page for articles that have no summary"

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=60)

    def handle(self, *args, limit=60, **opts):
        todo = []
        for a in Article.objects.select_related('source').order_by('-published')[:600]:
            if not clean_summary(a.summary, a.title):
                todo.append(a)
            if len(todo) >= limit:
                break
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda a: fetch_description(a.link), todo))
        n = 0
        for a, text in zip(todo, results):
            if text:
                a.summary = text
                a.save(update_fields=['summary'])
                n += 1
        self.stdout.write(f"Added a summary to {n} of {len(todo)} articles.")
