import html as htmllib
import threading
import time
from datetime import timedelta

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.mail import send_mail
from django.core.management import call_command
from django.http import HttpResponse, HttpResponseForbidden

from django.contrib.syndication.views import Feed
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.html import strip_tags
from django.views.decorators.http import require_POST

from .models import Article, Category, Event, Firm, Market, Source, Story, Subscriber
from .summaries import fetch_description, probe
from .services import ROUND_RE, format_usd, is_fund_close, is_relevant, tidy


# ---------- helpers ----------

def story_qs():
    return (Story.objects.select_related('category', 'market')
            .prefetch_related('articles__source', 'firms'))


def decorate(stories):
    """Add 'also reported by' publishers and a readable fund size to each story."""
    for s in stories:
        seen = {s.publisher}
        s.also = []
        for a in s.articles.all():
            _, pub = tidy(a.title, a.source.name)
            if pub not in seen:
                seen.add(pub)
                s.also.append({'publisher': pub, 'link': a.link})
        s.amount_text = format_usd(s.amount_usd)
        pks = [a.pk for a in s.articles.all()]
        s.url = f"/story/{min(pks)}/" if pks else s.link
    return stories


def clean_summary(raw, title):
    text = htmllib.unescape(strip_tags(raw or ''))
    text = ' '.join(text.split())
    if len(text) < 50 or text.lower().startswith(title.lower()[:40]) and len(text) < len(title) + 40:
        return ''
    return text if len(text) <= 520 else text[:520].rsplit(' ', 1)[0] + '…'


_summary_tried = {}  # article id -> time we last tried to fetch its summary


def story_page(request, pk):
    article = get_object_or_404(Article.objects.select_related('story'), pk=pk)
    if not article.story_id:
        return redirect(article.link)
    story = decorate([story_qs().get(pk=article.story_id)])[0]
    arts = sorted(story.articles.all(), key=lambda a: a.published)
    # Fetch a missing summary from the publisher's page the first time a story is opened
    for a in arts[:3]:
        if not clean_summary(a.summary, a.title):
            if time.time() - _summary_tried.get(a.pk, 0) < 6 * 3600:
                continue  # already tried recently; do not slow the page down again
            _summary_tried[a.pk] = time.time()
            text = fetch_description(a.link, timeout=5)
            if text:
                a.summary = text
                a.save(update_fields=['summary'])
    notes = []
    for a in arts:
        title, pub = tidy(a.title, a.source.name)
        notes.append({'publisher': pub, 'link': a.link, 'title': title,
                      'published': a.published, 'text': clean_summary(a.summary, title)})
    first = notes[0] if notes else {'publisher': story.publisher, 'link': story.link, 'published': story.published}
    texts = [n for n in notes if n['text']]
    now = timezone.now()
    latest = decorate([x for x in story_qs()[:120] if is_relevant(x) and x.pk != story.pk][:10])
    return render(request, 'news/story.html', base_ctx(
        request, story=story, first=first, notes=notes, texts=texts[:3],
        latest=latest, heading=story.title))


def base_ctx(request, section='news', **extra):
    ctx = {
        'section': section,
        'categories': Category.objects.annotate(n=Count('story')),
        'markets': Market.objects.annotate(n=Count('story')),
        'total': Story.objects.count(),
        'q': request.GET.get('q', '').strip(),
        'subscribed': request.GET.get('subscribed'),
        'current': None,
        'current_market': None,
    }
    ctx.update(extra)
    return ctx


def score(story, now):
    """Rank stories: more publishers, bigger money and newer all score higher."""
    age_hours = max((now - story.published).total_seconds() / 3600, 0)
    big = 5 if story.amount_usd and story.amount_usd >= 1e9 else 0
    startup_round = -15 if ROUND_RE.search(story.title) else 0  # keep fund news on top
    return story.article_count * 10 + big + startup_round - age_hours * 0.4


# ---------- news pages ----------

def home(request):
    q = request.GET.get('q', '').strip()
    if q:
        items = decorate(list(story_qs().filter(title__icontains=q)[:60]))
        return render(request, 'news/home.html', base_ctx(
            request, mode='list', items=items,
            heading=f"{len(items)} result{'s' if len(items) != 1 else ''} for “{q}”"))

    now = timezone.now()
    recent = decorate([s for s in story_qs()[:300] if is_relevant(s)][:200])
    ranked = sorted(recent, key=lambda s: score(s, now), reverse=True)[:6]
    lead = ranked[0] if ranked else None
    top = ranked[1:]
    shown = {s.id for s in ranked}
    feed = [s for s in recent if s.id not in shown][:30]

    sections = []
    for c in Category.objects.all():
        stories = [s for s in recent if s.category_id == c.id][:5]
        if stories:
            sections.append({'name': c.name, 'stories': stories})

    return render(request, 'news/home.html', base_ctx(
        request, mode='home', lead=lead, top=top, items=feed, sections=sections))


def category_page(request, category):
    cat = get_object_or_404(Category, name__iexact=category)
    items = decorate(list(story_qs().filter(category=cat)[:80]))
    return render(request, 'news/home.html', base_ctx(
        request, mode='list', items=items, heading=cat.name, current=cat.name,
        sub=f"Latest {cat.name.lower()} stories from every source we follow."))


def market_page(request, slug):
    market = get_object_or_404(Market, slug=slug)
    items = decorate(list(story_qs().filter(market=market)[:80]))
    return render(request, 'news/home.html', base_ctx(
        request, mode='list', items=items, heading=market.name, current_market=market.slug,
        sub=f"Fund news for {market.name.lower()}."))


# ---------- firms ----------

def firm_list(request):
    firms = Firm.objects.annotate(n=Count('story'))
    groups = {}
    for f in firms:
        groups.setdefault(f.name[0].upper(), []).append(f)
    letters = sorted(groups.items())
    return render(request, 'news/firms.html', base_ctx(
        request, section='firms', letters=letters, heading='Firms A to Z',
        sub='Every firm we track, with the number of stories that mention it.'))


def firm_page(request, slug):
    firm = get_object_or_404(Firm, slug=slug)
    items = decorate(list(story_qs().filter(firms=firm)[:80]))
    return render(request, 'news/home.html', base_ctx(
        request, section='firms', mode='list', items=items, heading=firm.name,
        sub=f"{len(items)} stor{'y' if len(items) == 1 else 'ies'} mentioning {firm.name}."))


# ---------- events ----------

def events(request):
    today = timezone.localdate()
    past = request.GET.get('past') == '1'
    qs = Event.objects.filter(start_date__lt=today).order_by('-start_date') if past \
        else Event.objects.filter(start_date__gte=today)
    return render(request, 'news/events.html', base_ctx(
        request, section='events', events=qs, past=past,
        heading='Events', sub='Conferences, roundtables and webinars across private markets.'))


# ---------- largest closes ----------

def closes(request):
    try:
        days = int(request.GET.get('days', 30))
    except ValueError:
        days = 30
    if days not in (7, 30, 90):
        days = 30
    since = timezone.now() - timedelta(days=days)
    qs = story_qs().filter(published__gte=since, category__name__iexact='Fundraising',
                           amount_usd__isnull=False)
    rows = [s for s in qs if is_fund_close(s.title)]
    decorate(rows)
    rows.sort(key=lambda s: s.amount_usd, reverse=True)

    by_market = {}
    for s in rows:
        name = s.market.name if s.market else 'Other'
        by_market[name] = by_market.get(name, 0) + s.amount_usd
    ordered = sorted(by_market.items(), key=lambda kv: kv[1], reverse=True)
    biggest = ordered[0][1] if ordered else 1
    bars = [{'name': n, 'text': format_usd(v), 'pct': max(round(v / biggest * 100), 2)}
            for n, v in ordered]

    return render(request, 'news/closes.html', base_ctx(
        request, section='closes', rows=rows[:15], bars=bars, days=days,
        total_text=format_usd(sum(s.amount_usd for s in rows)) or '$0', count=len(rows),
        heading='Largest fund closes',
        sub='Fund sizes read from headlines of stories about closes and raises.'))


# ---------- newsletter, about, feed ----------

@require_POST
def subscribe(request):
    email = request.POST.get('email', '').strip().lower()
    try:
        validate_email(email)
    except ValidationError:
        return redirect('/?subscribed=invalid')
    Subscriber.objects.get_or_create(email=email)
    return redirect('/?subscribed=ok')


def about(request):
    return render(request, 'news/about.html', base_ctx(
        request, section='about', heading='About Fund News',
        source_count=Source.objects.count(), story_count=Story.objects.count(),
        firm_count=Firm.objects.count()))


class LatestStories(Feed):
    title = "Fund News"
    link = "/"
    description = "Latest private markets and fund stories."

    def items(self):
        return Story.objects.order_by('-published')[:40]

    def item_title(self, item):
        return item.title

    def item_link(self, item):
        return item.link

    def item_description(self, item):
        return f"{item.publisher}"

    def item_pubdate(self, item):
        return item.published


# ---------- hourly refresh (called by a scheduled job) ----------

_refresh_lock = threading.Lock()
_last_refresh = 0.0
MIN_GAP = 50 * 60  # seconds between real fetches; the ping itself keeps the site awake


def _run_refresh():
    try:
        call_command('fetch_news')
        call_command('organize')
        call_command('fill_summaries', limit=40)
    finally:
        _refresh_lock.release()


def refresh(request, token):
    """Starts a news fetch in the background. Needs the secret token."""
    if not settings.REFRESH_TOKEN or token != settings.REFRESH_TOKEN:
        return HttpResponseForbidden('Wrong token')
    global _last_refresh
    if time.time() - _last_refresh < MIN_GAP:
        return HttpResponse('Fetched recently, nothing to do', status=200)
    if not _refresh_lock.acquire(blocking=False):
        return HttpResponse('A refresh is already running', status=202)
    _last_refresh = time.time()
    threading.Thread(target=_run_refresh, daemon=True).start()
    return HttpResponse('Refresh started', status=202)


# ---------- daily newsletter (called by a scheduled job) ----------

_digest_lock = threading.Lock()
_last_digest = 0.0
DIGEST_GAP = 20 * 3600  # never send the digest twice within 20 hours


def _run_digest(site):
    try:
        call_command('send_digest', site=site)
    finally:
        _digest_lock.release()


def send_digest_hook(request, token):
    """Starts sending the daily email in the background. Needs the secret token."""
    global _last_digest
    if not settings.REFRESH_TOKEN or token != settings.REFRESH_TOKEN:
        return HttpResponseForbidden('Wrong token')
    if time.time() - _last_digest < DIGEST_GAP:
        return HttpResponse('Already sent recently, nothing to do', status=200)
    if not _digest_lock.acquire(blocking=False):
        return HttpResponse('A send is already running', status=202)
    _last_digest = time.time()
    site = request.build_absolute_uri('/').rstrip('/')
    threading.Thread(target=_run_digest, args=(site,), daemon=True).start()
    return HttpResponse('Digest started', status=202)


def unsubscribe(request, token):
    """Removes a subscriber. The link in each email carries a signed address."""
    try:
        email = signing.loads(token, salt='unsubscribe')
    except signing.BadSignature:
        return HttpResponse('This unsubscribe link is not valid.', status=400)
    Subscriber.objects.filter(email=email).delete()
    return HttpResponse(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Unsubscribed</title>'
        '<body style="font-family:Georgia,serif;background:#FBF4E4;color:#3B2C1E;max-width:30rem;margin:4rem auto;padding:0 1rem">'
        '<h1>You are unsubscribed</h1><p>We will not send you any more emails.</p>'
        '<p><a href="/" style="color:#8F4F12">Back to Fund News</a></p></body>')


# ---------- email test page (editors only) ----------

@staff_member_required
def test_email(request):
    """Sends one test email and shows the result or the exact error. Editors only."""
    to = request.GET.get('to', '').strip()
    backend = settings.MAILERS['default']['BACKEND'].rsplit('.', 1)[-1]
    api_key = settings.BREVO_API_KEY
    info = [
        f"Sending method: {backend}",
        f"Brevo API key set: {bool(api_key)}, length {len(api_key)}, starts with xkeysib-: {api_key.startswith('xkeysib-')}",
        f"From: {settings.DEFAULT_FROM_EMAIL}",
    ]
    if not to:
        info.append("")
        info.append("Add ?to=your@email.com to the address to send a test email.")
        return HttpResponse("\n".join(info), content_type='text/plain')
    try:
        send_mail('Fund News test email', 'If you can read this, sending works.', None, [to])
        info.append(f"\nRESULT: sent to {to}. Check the inbox and the spam folder.")
    except Exception as exc:
        info.append(f"\nRESULT: FAILED\n{type(exc).__name__}: {exc}")
    return HttpResponse("\n".join(info), content_type='text/plain')


@staff_member_required
def test_summaries(request):
    """Staff-only page: shows what happens when we fetch summaries from publishers."""
    from concurrent.futures import ThreadPoolExecutor
    arts = [a for a in Article.objects.select_related('source').order_by('-published')[:200]
            if not clean_summary(a.summary, a.title)][:10]
    with ThreadPoolExecutor(max_workers=5) as pool:
        notes = list(pool.map(lambda a: probe(a.link), arts))
    total = Article.objects.count()
    have = sum(1 for a in Article.objects.order_by('-published')[:200] if clean_summary(a.summary, a.title))
    lines = [f"Of the newest 200 articles, {have} have a summary. Articles in total: {total}.", ""]
    for a, n in zip(arts, notes):
        lines.append(f"{a.source.name} | {a.link[:70]}\n    -> {n}")
    return HttpResponse("\n".join(lines), content_type='text/plain; charset=utf-8')
