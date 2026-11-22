"""Read the short description a publisher puts in its own page (the text that
search engines show under a headline). Used when the news feed has no summary."""
import html as htmllib
import re
import urllib.request
from urllib.parse import urlparse

META_RE = re.compile(r'<meta\b[^>]*>', re.I)
ATTR_RE = re.compile(r'([a-zA-Z:_-]+)\s*=\s*("([^"]*)"|\'([^\']*)\')')
WANTED = ('og:description', 'twitter:description', 'description')
UA = 'Mozilla/5.0 (compatible; FundNewsBot/1.0; +https://fundnews.onrender.com/about/)'


def is_google(url):
    host = urlparse(url).netloc.lower()
    return host == 'google.com' or host.endswith('.google.com')


def resolve_google(url, timeout=8):
    """Turn a Google News redirect link into the publisher's real article address."""
    try:
        from googlenewsdecoder import gnewsdecoder
        r = gnewsdecoder(url, timeout=timeout)
        if r.get('success') and r.get('decoded_url'):
            return r['decoded_url']
    except Exception:
        pass
    return ''


def fetch_description(url, timeout=6):
    if is_google(url):
        url = resolve_google(url)
    if not url or not url.startswith('http') or is_google(url):
        return ''
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if 'html' not in (r.headers.get('Content-Type') or ''):
                return ''
            raw = r.read(250_000)
    except Exception:
        return ''
    page = raw.decode('utf-8', errors='ignore')
    head = page[:page.lower().find('</head>')] if '</head>' in page.lower() else page
    found = {}
    for tag in META_RE.findall(head):
        attrs = {m.group(1).lower(): (m.group(3) if m.group(3) is not None else m.group(4))
                 for m in ATTR_RE.finditer(tag)}
        key = (attrs.get('property') or attrs.get('name') or '').lower()
        if key in WANTED and attrs.get('content'):
            found.setdefault(key, attrs['content'])
    for key in WANTED:
        if key in found:
            text = ' '.join(htmllib.unescape(found[key]).split())
            if len(text) >= 40:
                return text[:600]
    return ''


def probe(url, timeout=6):
    """Like fetch_description but says what happened. Used by the staff test page."""
    if is_google(url):
        real = resolve_google(url)
        if not real:
            return 'failed: could not find the real article address behind the Google News link'
        url = real
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = r.headers.get('Content-Type') or ''
            raw = r.read(250_000)
            final = r.geturl()
    except Exception as e:
        return f'failed: {type(e).__name__}: {e}'[:200]
    text = fetch_description(url, timeout)
    if text:
        return 'OK: ' + text[:120]
    return f'page loaded ({len(raw)} bytes, {ctype[:30]}) but no description tag found'
