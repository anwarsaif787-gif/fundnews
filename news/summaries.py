"""Read the short description a publisher puts in its own page (the text that
search engines show under a headline). Used when the news feed has no summary."""
import html as htmllib
import json
import re
import urllib.request
from urllib.parse import urlparse

META_RE = re.compile(r'<meta\b[^>]*>', re.I)
WANTED = ('og:description', 'twitter:description', 'description', 'dc.description')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/124.0 Safari/537.36')
HEADERS = {'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml',
           'Accept-Language': 'en-US,en;q=0.9', 'Referer': 'https://www.google.com/'}
LD_RE = re.compile(r'"description"\s*:\s*"((?:[^"\\]|\\.){40,800})"')
ATTR_RE = re.compile(r'([a-zA-Z:_-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s"\'>]+))')


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
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if 'html' not in (r.headers.get('Content-Type') or ''):
                return ''
            raw = r.read(400_000)
    except Exception:
        return ''
    page = raw.decode('utf-8', errors='ignore')
    head = page[:page.lower().find('</head>')] if '</head>' in page.lower() else page
    found = {}
    for tag in META_RE.findall(head):
        attrs = {m.group(1).lower(): next((g for g in m.groups()[1:] if g is not None), '')
                 for m in ATTR_RE.finditer(tag)}
        key = (attrs.get('property') or attrs.get('name') or attrs.get('itemprop') or '').lower()
        if key in WANTED and attrs.get('content'):
            found.setdefault(key, attrs['content'])
    for key in WANTED + ('itemprop-description',):
        if key in found:
            text = ' '.join(htmllib.unescape(found[key]).split())
            if len(text) >= 40:
                return text[:600]
    # Last resort: the description inside the page's structured data (JSON-LD)
    for m in LD_RE.finditer(page):
        try:
            text = ' '.join(htmllib.unescape(json.loads('"' + m.group(1) + '"')).split())
        except Exception:
            continue
        if len(text) >= 60 and '<' not in text:
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
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = r.headers.get('Content-Type') or ''
            raw = r.read(400_000)
            final = r.geturl()
    except Exception as e:
        return f'failed: {type(e).__name__}: {e}'[:200]
    text = fetch_description(url, timeout)
    if text:
        return 'OK: ' + text[:120]
    return f'page loaded ({len(raw)} bytes, {ctype[:30]}) but no description tag found'
