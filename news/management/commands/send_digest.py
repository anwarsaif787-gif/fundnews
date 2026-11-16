from datetime import timedelta
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone
from news.models import Story, Subscriber


class Command(BaseCommand):
    help = "Email the top stories of the last 24 hours to every subscriber"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Print the email, send nothing')
        parser.add_argument('--site', default='http://127.0.0.1:8000', help='Your website address')

    def handle(self, *args, **opts):
        since = timezone.now() - timedelta(hours=24)
        stories = list(Story.objects.filter(published__gte=since)
                       .order_by('-article_count', '-published')[:10])
        if not stories:
            self.stdout.write("No stories in the last 24 hours. Nothing to send.")
            return
        lines = [f"- {s.title} ({s.publisher})\n  {s.link}" for s in stories]
        body = "Top fund news today\n\n" + "\n\n".join(lines) + f"\n\nMore at {opts['site']}\n"
        subject = "Fund News: today's top stories"
        if opts['dry_run']:
            self.stdout.write(f"{subject}\n\n{body}")
            return
        emails = list(Subscriber.objects.values_list('email', flat=True))
        for email in emails:
            send_mail(subject, body, None, [email])
        self.stdout.write(f"Sent to {len(emails)} subscriber(s).")
