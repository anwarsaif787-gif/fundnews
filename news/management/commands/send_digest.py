from datetime import timedelta
from html import escape

from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import Story, Subscriber


class Command(BaseCommand):
    help = "Email the top stories of the last 24 hours to every subscriber"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Print the email, send nothing')
        parser.add_argument('--site', default='http://127.0.0.1:8000', help='Your website address')

    def handle(self, *args, **opts):
        site = opts['site'].rstrip('/')
        since = timezone.now() - timedelta(hours=24)
        stories = list(Story.objects.filter(published__gte=since)
                       .order_by('-article_count', '-published')[:10])
        if not stories:
            self.stdout.write("No stories in the last 24 hours. Nothing to send.")
            return

        subject = "Fund News: today's top stories"
        text_lines = [f"- {s.title} ({s.publisher})\n  {s.link}" for s in stories]
        html_rows = "".join(
            f'<p style="margin:0 0 14px"><a href="{escape(s.link)}" style="color:#3B2C1E;font-size:17px;'
            f'font-weight:bold;text-decoration:none">{escape(s.title)}</a><br>'
            f'<span style="color:#8F4F12;font-size:13px">{escape(s.publisher)}</span></p>'
            for s in stories)

        def build(email):
            link = f"{site}/unsubscribe/{signing.dumps(email, salt='unsubscribe')}/"
            text = ("Top fund news today\n\n" + "\n\n".join(text_lines)
                    + f"\n\nMore at {site}\n\nUnsubscribe: {link}\n")
            html = (
                '<div style="background:#FBF4E4;padding:24px;font-family:Georgia,serif;color:#3B2C1E">'
                '<div style="max-width:560px;margin:auto">'
                '<h1 style="margin:0 0 4px;color:#5B4632">Fund News</h1>'
                '<p style="margin:0 0 20px;color:#8F4F12">Top private markets stories today</p>'
                f'{html_rows}'
                f'<p style="margin-top:24px"><a href="{site}" style="color:#C8792C">More stories on the site</a></p>'
                f'<p style="font-size:12px;color:#7a6a58">You get this because you signed up on Fund News. '
                f'<a href="{link}" style="color:#7a6a58">Unsubscribe</a></p>'
                '</div></div>')
            return text, html, link

        if opts['dry_run']:
            self.stdout.write(f"{subject}\n\n{build('reader@example.com')[0]}")
            return

        sent = failed = 0
        for email in Subscriber.objects.values_list('email', flat=True):
            text, html, link = build(email)
            msg = EmailMultiAlternatives(subject, text, None, [email],
                                         headers={'List-Unsubscribe': f'<{link}>'})
            msg.attach_alternative(html, 'text/html')
            try:
                msg.send()
                sent += 1
            except Exception as exc:  # one bad address should not stop the rest
                failed += 1
                self.stderr.write(f"Could not send to {email}: {exc}")
        self.stdout.write(f"Sent to {sent} subscriber(s), {failed} failed.")
