import re
import json
import os
import requests
from datetime import datetime, timedelta, timezone

SOURCES = {
    'PIB':  'site:pib.gov.in',
    'SEBI': 'site:sebi.gov.in',
    'RBI':  'site:rbi.org.in'
}

RSS_BASE = (
    'https://news.google.com/rss/search?q={query}'
    '&hl=en-IN&gl=IN&ceid=IN:en'
)

BLACKLIST = [
    'press release', 'nodal agency', 'about pib',
    'about sebi', 'about rbi', 'disclaimer',
    'annual report', 'weekly statistical', 'minutes of'
]

USED_FILE = 'used_articles.json'


def load_used_urls():
    """Load list of already-processed article URLs."""
    try:
        with open(USED_FILE, 'r') as f:
            return set(json.load(f))
    except Exception:
        return set()


def get_yesterday_window_ist():
    ist = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist)
    yesterday_ist = now_ist - timedelta(days=1)
    start_ist = yesterday_ist.replace(hour=0,  minute=0,  second=0,  microsecond=0)
    end_ist   = yesterday_ist.replace(hour=23, minute=59, second=59, microsecond=0)
    return start_ist.astimezone(timezone.utc), end_ist.astimezone(timezone.utc)


def fetch_articles():
    """
    Fetch one fresh article per source from yesterday.
    Skips articles already processed in previous runs.
    """
    start_utc, end_utc = get_yesterday_window_ist()
    used_urls = load_used_urls()

    print(f'  📅 Fetching articles for: {(datetime.now(timezone(timedelta(hours=5,minutes=30))) - timedelta(days=1)).strftime("%d %b %Y")} IST')
    print(f'  🚫 Skipping {len(used_urls)} already-used articles')

    results = []

    for source_name, query in SOURCES.items():
        print(f'  🔍 Fetching {source_name}...')
        article = _fetch_top_article(query, start_utc, end_utc,
                                     source_name, used_urls)
        if article:
            results.append(article)
            print(f'     ✅ {article["title"][:60]}')
        else:
            print(f'     ⚠️  No fresh article found for {source_name}')

    if not results:
        raise Exception('No fresh articles found. All may already be used.')

    return results


def _fetch_top_article(query, start_utc, end_utc, source_name, used_urls):
    url = RSS_BASE.format(query=requests.utils.quote(query))

    try:
        resp = requests.get(url, timeout=15,
                            headers={'User-Agent': 'Mozilla/5.0'})
        resp.raise_for_status()
    except Exception as e:
        print(f'     ⚠️  RSS fetch failed: {e}')
        return None

    items = re.findall(r'<item>(.*?)</item>', resp.text, re.DOTALL)

    for item in items:
        title = _extract_tag(item, 'title')
        link  = _extract_tag(item, 'link')
        desc  = _extract_tag(item, 'description')
        pub   = _extract_tag(item, 'pubDate')

        if not title or not pub:
            continue

        # Date filter
        try:
            pub_dt = datetime.strptime(pub, '%a, %d %b %Y %H:%M:%S %Z')
            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue

        if not (start_utc <= pub_dt <= end_utc):
            continue

        # Blacklist filter
        if any(b in title.lower() for b in BLACKLIST):
            continue

        # ── Skip already-used articles ──────────────────────────
        if link in used_urls:
            print(f'     ⏭️  Skipping (already used): {title[:50]}')
            continue

        return {
            'source':      source_name,
            'title':       _clean(title),
            'description': _clean(desc)[:800],
            'link':        link
        }

    return None


def _extract_tag(text, tag):
    match = re.search(rf'<{tag}[^>]*>(.*?)</{tag}>', text, re.DOTALL)
    if not match:
        return ''
    val = match.group(1).strip()
    val = re.sub(r'<[^>]+>', '', val)
    val = re.sub(r'<!\[CDATA\[|\]\]>', '', val)
    return val.strip()


def _clean(text):
    return re.sub(r'\s+', ' ', text).strip()
