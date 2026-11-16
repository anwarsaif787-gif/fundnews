from django.core.management.base import BaseCommand
from news.models import Article, Story
from news.services import is_noise, load_context, process_article


class Command(BaseCommand):
    help = "Group existing articles into stories and tag topics, markets, firms and fund sizes"

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Delete all stories and group every article again')

    def handle(self, *args, **opts):
        removed = 0
        for a in Article.objects.all():
            if is_noise(a.title):
                a.delete()
                removed += 1
        if removed:
            self.stdout.write(f"Removed {removed} items that are not news (filing notices, login pages...).")
        if opts['reset']:
            Story.objects.all().delete()
        else:
            Story.objects.filter(articles__isnull=True).delete()
        ctx = load_context()
        n = 0
        for a in (Article.objects.filter(story__isnull=True)
                  .select_related('source').order_by('published')):
            process_article(a, ctx)
            n += 1
        self.stdout.write(f"Organized {n} articles into {Story.objects.count()} stories.")
