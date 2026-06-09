# ================================================================
#  fetch_articles.py — Google News RSS Article Fetcher
#  Fetches yesterday's top article from PIB, SEBI, RBI
#  Same Google News RSS approach as System 1 (UPSC Automation)
# ================================================================

import re
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

# Boilerplate titles to skip
BLACKLIST = [
    'press release', 'nodal agency', 'about pib',
    'about sebi', 'about rbi', 'disclaimer', 'annual report',
    'weekly statistical', 'minutes of'
]


def get_yesterday_window_ist():
    """Return (start_utc, end_utc) for yesterday in IST."""
    ist = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist)
    yesterday_ist = now_ist - timedelta(days=1)

    start_ist = yesterday_ist.replace(hour=0,  minute=0,  second=0,  microsecond=0)
    end_ist   = yesterday_ist.replace(hour=23, minute=59, second=59, microsecond=0)

    return start_ist.astimezone(timezone.utc), end_ist.astimezone(timezone.utc)


def fetch_articles():
    """
    Fetch one article per source from yesterday.
    Returns list of dicts: [{source, title, description, link}, ...]
    """
    start_utc, end_utc = get_yesterday_window_ist()
    print(f'  📅 Fetching articles for: {start_utc.strftime("%d %b %Y")} IST')

    results = []

    for source_name, query in SOURCES.items():
        print(f'  🔍 Fetching {source_name}...')
        article = _fetch_top_article(query, start_utc, end_utc, source_name)
        if article:
            results.append(article)
            print(f'     ✅ {article["title"][:60]}')
        else:
            print(f'     ⚠️  No article found for {source_name} yesterday')

    if not results:
        raise Exception('No articles found from any source for yesterday.')

    return results


def _fetch_top_article(query, start_utc, end_utc, source_name):
    """Fetch top valid article from Google News RSS for a query."""
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

        # Date filter — yesterday IST
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
    val = re.sub(r'<[^>]+>', '', val)          # strip HTML tags
    val = re.sub(r'<!\[CDATA\[|\]\]>', '', val) # strip CDATA
    return val.strip()


def _clean(text):
    return re.sub(r'\s+', ' ', text).strip()
