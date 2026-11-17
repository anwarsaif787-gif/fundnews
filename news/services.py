"""Sorting logic: tidy headlines, pick topic and market, spot firms,
read fund sizes and group reports of the same event into one Story."""
import re
from datetime import timedelta

from .models import Category, Firm, Market, Story

# Some sites refuse requests that don't look like a browser or feed reader.
FEED_AGENT = 'Mozilla/5.0 (compatible; FundNews/1.0; +http://127.0.0.1:8000)'

# Approximate exchange rates used only to rank fund sizes. Edit as needed.
FX = {'$': 1.0, 'us$': 1.0, '€': 1.08, '£': 1.27}
UNIT = {'trillion': 1e12, 'tn': 1e12, 'billion': 1e9, 'bn': 1e9, 'b': 1e9,
        'million': 1e6, 'mn': 1e6, 'm': 1e6}

AMOUNT_RE = re.compile(
    r'(US\$|\$|€|£)\s?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s?'
    r'(trillion|billion|million|tn|bn|mn|b|m)\b', re.I)

# Indian rupees: "Rs 192 Cr", "Rs. 500 crore", "₹1,200 crore", "INR 50 lakh".
INR_PER_USD = 88.0  # approximate; edit as needed
INR_RE = re.compile(
    r'(?:Rs\.?|₹|INR)\s?(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s?'
    r'(crores?|cr|lakhs?|lacs?|million|mn|billion|bn)\b', re.I)
INR_UNIT = {'crore': 1e7, 'crores': 1e7, 'cr': 1e7, 'lakh': 1e5, 'lakhs': 1e5, 'lac': 1e5, 'lacs': 1e5,
            'million': 1e6, 'mn': 1e6, 'billion': 1e9, 'bn': 1e9}

# "first close of a $500m fund": the amount raised is the smaller figure, not the target.
PARTIAL_RE = re.compile(r'\b(first|interim|initial)\s+close\b', re.I)

# Words that suggest a fund really closed or raised money (not just "targets").
CLOSE_RE = re.compile(
    r'\b(clos(?:e|es|ed|ing)|raise[sd]?|secures?|secured|hard cap|lands)\b', re.I)

# Startup funding rounds (a company raising money), not funds closing.
ROUND_RE = re.compile(
    r'\b(seed|pre-seed|series\s+[a-h]|funding round|in funding|equity funding|bridge round|angel round)\b',
    re.I)

# Words too common in fund news to prove two headlines are the same event.
GENERIC = set('raise raises raised raising funding fund funds round amt close closes closed '
              'launch launches launched announce announces announced invest investment investments '
              'capital partner partners group management private equity venture ventures credit '
              'debt real estate infrastructure global first final debut new series seed '
              'million billion billions firm firms deal deals buyout stake stakes acquire acquires '
              'acquisition appoint appoints appointed hire hires names named joins join '
              'target targets targeting secures secure lands says report reports'.split())

# Things that are not news stories: SEC filing notices ("Form 4 ..."), login and
# subscribe pages, and website front pages that Google News sometimes returns.
NOISE_RE = re.compile(
    r'^\s*(form\s+([0-9]|s-|n-)|sign[ -]?in\b|log[ -]?in\b|subscribe\b)'
    r'|stories about startups|^\s*yourstory\s*\|'
    r'|\b(daily|weekly|morning|evening)\s+(roundup|round-up|digest|briefing|wrap)\b|\bnews and updates\b'
    r'|\b(startup\s+)?ecosystem\s+profile\b|\bprofile\s+20\d\d\b', re.I)


def is_noise(title):
    head = tidy(title, '')[0]
    return bool(NOISE_RE.search(head)) or len(head.split()) < 3


# Words that show a story is about funds or investing. Stories with none of these,
# no topic, no market and no tracked firm are kept out of the home page.
FUND_RE = re.compile(
    r'\b(funds?|fundrais\w*|capital|invest\w*|equity|buyouts?|stakes?|ventures?|vc|vcs|lps?|gps?|'
    r'asset managers?|asset management|private credit|secondar\w+|limited partners?|sovereign|pension|'
    r'endowment|portfolio|commitments?|co-invest\w*|carried interest|aum|raises?|raised)\b', re.I)


def is_relevant(story):
    """True if the story is about funds or investing (used to filter the home page)."""
    return bool(story.category_id or story.market_id or story.firms.all()
                or FUND_RE.search(story.title))


def is_fund_close(title):
    return bool(CLOSE_RE.search(title)) and not ROUND_RE.search(title)


STOP = set('the and for with from into over after says say new its this that '
           'has have will are was were been than also more most'.split())


def tidy(title, source_name):
    """Google News titles end with ' - Publisher'. Split that off."""
    if ' - ' in title:
        head, tail = title.rsplit(' - ', 1)
        if 0 < len(tail) <= 40:
            return head, tail
    return title, source_name


def parse_amount(title):
    """Money amount in the headline, in US dollars (approx), or None.

    With several amounts the largest is used, except for a first or interim
    close, where the smallest is the amount actually raised."""
    values = []
    for cur, num, unit in AMOUNT_RE.findall(title):
        values.append(float(num.replace(',', '')) * UNIT[unit.lower()] * FX[cur.lower()])
    for num, unit in INR_RE.findall(title):
        rupees = float(num.replace(',', '')) * INR_UNIT[unit.lower()]
        values.append(rupees / INR_PER_USD)
    if not values:
        return None
    return min(values) if (len(values) > 1 and PARTIAL_RE.search(title)) else max(values)


def format_usd(value):
    if not value:
        return ''
    if value >= 1e9:
        return f"${value / 1e9:.1f}B"
    if value >= 1e6:
        return f"${value / 1e6:.0f}M"
    return f"${value / 1e3:.0f}K"


def keyword_match(text, keywords):
    for word in keywords.split(','):
        word = word.strip().lower()
        if word and re.search(r'\b' + re.escape(word) + r'\b', text):
            return True
    return False


def tokens(title):
    text = INR_RE.sub(' amt ', AMOUNT_RE.sub(' amt ', title))
    text = text.lower()
    out = set()
    for w in re.findall(r'[a-z0-9]+', text):
        if len(w) > 2 and w not in STOP:
            if w.endswith('s') and len(w) > 4:
                w = w[:-1]
            out.add(w)
    return out


def load_context():
    firms = []
    for f in Firm.objects.all():
        names = [f.name] + [a for a in f.aliases.split(',')]
        pats = [re.compile(r'\b' + re.escape(n.strip()) + r'\b', re.I) for n in names if n.strip()]
        firms.append((f, pats))
    return {
        'categories': list(Category.objects.all()),
        'markets': list(Market.objects.all()),
        'firms': firms,
    }


def find_story(title, published, firm_ids, amount=None):
    """Find an existing Story about the same event, or None.

    Generic words ("raises", "funding", "fund") are ignored when comparing, and
    two headlines need at least two distinctive words in common (a firm or
    company name, a place, a product), so unrelated deals do not merge."""
    tok = tokens(title) - GENERIC
    if not tok:
        return None
    window = timedelta(days=3)
    best, best_sim = None, 0
    qs = Story.objects.filter(published__gte=published - window,
                              published__lte=published + window).prefetch_related('firms')
    for s in qs:
        other = tokens(s.title) - GENERIC
        if not other:
            continue
        common = tok & other
        sim = len(common) / len(tok | other)
        shared_firm = bool({f.id for f in s.firms.all()} & firm_ids)
        same_size = bool(amount and s.amount_usd and
                         abs(amount - s.amount_usd) / max(amount, s.amount_usd) < 0.02)
        match = (
            (len(common) >= 2 and sim >= 0.4)
            or (shared_firm and len(common) >= 2 and sim >= 0.25)
            or (shared_firm and same_size)
        )
        if match and sim > best_sim:
            best, best_sim = s, sim
    return best


def process_article(article, ctx=None):
    """Give an article its topic, market, firms and a Story. Safe to re-run."""
    if article.story_id:
        return article.story
    ctx = ctx or load_context()
    title, publisher = tidy(article.title, article.source.name)
    text = title.lower()  # headline only, without the ' - Publisher' ending

    category = article.category
    if category is None:
        category = next((c for c in ctx['categories'] if keyword_match(text, c.keywords)), None)
    market = next((m for m in ctx['markets'] if keyword_match(text, m.keywords)), None)
    firms = [f for f, pats in ctx['firms'] if any(p.search(title) for p in pats)]
    amount = parse_amount(title)
    firm_ids = {f.id for f in firms}

    story = find_story(title, article.published, firm_ids, amount)
    if story:
        story.article_count += 1
        if article.published > story.published:
            story.published = article.published
        if story.category is None and category:
            story.category = category
        if story.market is None and market:
            story.market = market
        if amount and (story.amount_usd is None or amount < story.amount_usd):
            story.amount_usd = amount  # when reports differ, use the lower figure
        story.save()
        story.firms.add(*firms)
    else:
        story = Story.objects.create(
            title=title[:300], link=article.link, publisher=publisher[:100],
            category=category, market=market, amount_usd=amount,
            published=article.published)
        story.firms.set(firms)

    article.story = story
    article.category = category
    article.save(update_fields=['story', 'category'])
    return story
