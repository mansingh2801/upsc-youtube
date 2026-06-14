#!/usr/bin/env python3
"""
system1_pipeline.py — v2
Triggered by repository_dispatch (event_type: system1_video).
Env vars: VIDEO_TITLE, VIDEO_SCRIPT, AUDIO_URL, ARTICLE_LINK (optional)

Flow:
  1. If ARTICLE_LINK present → resolve Google News URL → fetch full PIB text
  2. Regenerate richer Gemini script from full text (fallback: VIDEO_SCRIPT)
  3. Download Sarvam audio
  4. Build slideshow Short
  5. Upload to @iasbrief

Does NOT touch any System 2 file.
"""

import os, sys, json, re, subprocess, requests, time
from pathlib import Path

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("bs4 not available — regex-only URL parsing")

# ── CONSTANTS ────────────────────────────────────────────────

BG_COLOR     = '0D1B2A'
ACCENT_COLOR = 'F4A261'
TEXT_COLOR   = 'FFFFFF'
DIM_COLOR    = 'AAAAAA'
W, H, FPS    = 1080, 1920, 30
FONT         = 'Sans'

GEMINI_KEY   = os.environ.get('GEMINI_API_KEY', '')
GEMINI_MODEL = 'gemini-2.0-flash'
GEMINI_URL   = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent'

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.google.com/',
}


# ── 0. FULL ARTICLE FETCH ────────────────────────────────────

def resolve_google_news_url(google_url):
    """Extract real PIB URL from a Google News redirect page."""
    print(f"Resolving: {google_url[:80]}...")
    try:
        resp = requests.get(google_url, headers=BROWSER_HEADERS,
                            allow_redirects=True, timeout=15)

        # Best case: requests followed a real HTTP redirect to PIB
        if 'pib.gov.in' in resp.url:
            print(f"Direct redirect worked: {resp.url}")
            return resp.url

        html = resp.text

        # meta refresh: content="0; url=..."
        m = re.search(r'(?i)content=["\']?\d+;\s*url=([^"\'>\s]+)', html)
        if m:
            url = m.group(1).strip()
            if 'pib.gov.in' in url:
                print(f"Meta refresh match: {url}")
                return url

        # Any href containing pib.gov.in
        m = re.search(r'href=["\']([^"\']*pib\.gov\.in[^"\']*)["\']', html)
        if m:
            print(f"Href match: {m.group(1)}")
            return m.group(1)

        # BeautifulSoup sweep (if available)
        if BS4_AVAILABLE:
            soup = BeautifulSoup(html, 'html.parser')
            for a in soup.find_all('a', href=True):
                if 'pib.gov.in' in a['href']:
                    print(f"BS4 match: {a['href']}")
                    return a['href']

        print("Could not extract PIB URL from Google News page")

    except Exception as e:
        print(f"URL resolve error: {e}")

    return None


def fetch_full_article_text(pib_url):
    """Fetch full PIB article text. Jina primary, direct fetch fallback."""

    # Primary: Jina.ai — confirmed HTTP 200, ~7500 chars for PIB press releases
    try:
        jina_url = f'https://r.jina.ai/{pib_url}'
        print(f"Trying Jina: {jina_url[:80]}...")
        resp = requests.get(jina_url, timeout=30)
        if resp.status_code == 200 and len(resp.text) > 500:
            print(f"Jina OK: {len(resp.text):,} chars")
            return resp.text
        print(f"Jina: {resp.status_code} / {len(resp.text)} chars — trying fallback")
    except Exception as e:
        print(f"Jina failed: {e}")

    # Fallback: direct fetch — GitHub runner IPs bypass PIB Cloudflare
    try:
        print(f"Trying direct fetch: {pib_url[:80]}...")
        resp = requests.get(pib_url, headers=BROWSER_HEADERS, timeout=20)
        if resp.status_code == 200 and len(resp.text) > 500:
            print(f"Direct fetch OK: {len(resp.text):,} chars")
            return resp.text
        print(f"Direct fetch: {resp.status_code}")
    except Exception as e:
        print(f"Direct fetch failed: {e}")

    return None


def generate_script_from_full_text(title, full_text):
    """Call Gemini to produce a 5-point Shorts script from full article text."""
    if not GEMINI_KEY:
        print("No GEMINI_API_KEY — skipping script upgrade")
        return None

    prompt = f"""You are a UPSC current affairs educator. Generate a YouTube Shorts script from this PIB press release.

RULES:
- Exactly 5 lines. No bullets, numbers, symbols, or markdown.
- Each line: one clear fact or insight, max 12 words.
- Line 1 must be the single most important fact.
- Include UPSC-relevant angle: GS paper, policy, scheme, or constitutional significance.
- Plain text only. Nothing else in your response.

TITLE: {title}

ARTICLE:
{full_text[:4000]}

Output only the 5 lines, one per line."""

    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'temperature': 0.4, 'maxOutputTokens': 300}
    }

    for attempt in range(3):
        try:
            resp = requests.post(
                f'{GEMINI_URL}?key={GEMINI_KEY}',
                json=payload, timeout=30
            )
            if resp.status_code == 200:
                data = resp.json()
                raw = data['candidates'][0]['content']['parts'][0]['text'].strip()
                lines = [l.strip() for l in raw.split('\n') if l.strip()]
                if len(lines) >= 3:
                    print(f"Gemini script: {len(lines)} points generated")
                    return '\n'.join(lines)
                print(f"Gemini returned too few lines ({len(lines)}) — discarding")
                return None
            elif resp.status_code == 503:
                wait = 20 * (attempt + 1)
                print(f"Gemini 503 — retry in {wait}s...")
                time.sleep(wait)
            else:
                print(f"Gemini error {resp.status_code}: {resp.text[:200]}")
                break
        except Exception as e:
            print(f"Gemini attempt {attempt+1} failed: {e}")
            time.sleep(10)

    return None


# ── 1. DOWNLOAD AUDIO ────────────────────────────────────────

def download_audio(url, dest='output/voice.wav'):
    Path('output').mkdir(exist_ok=True)
    print("Downloading Sarvam audio from Drive...")
    session = requests.Session()
    resp = session.get(url, stream=True, timeout=60, allow_redirects=True)

    # Handle Google Drive large-file confirm page
    if 'text/html' in resp.headers.get('Content-Type', ''):
        for key, val in resp.cookies.items():
            if key.startswith('download_warning'):
                resp = session.get(f"{url}&confirm={val}", stream=True, timeout=60)
                break

    resp.raise_for_status()
    with open(dest, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    size = os.path.getsize(dest)
    print(f"Audio saved: {size:,} bytes → {dest}")
    if size < 2000:
        raise RuntimeError(f"Audio too small ({size}B) — Drive download likely failed")
    return dest


# ── 2. VIDEO BUILDER ─────────────────────────────────────────

def get_duration(path):
    result = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', path],
        capture_output=True, text=True, check=True
    )
    for s in json.loads(result.stdout).get('streams', []):
        if 'duration' in s:
            return float(s['duration'])
    raise RuntimeError("Cannot read audio duration")


def parse_points(script, max_pts=5):
    lines = [l.strip() for l in script.split('\n') if len(l.strip()) > 15]
    if len(lines) >= 3:
        return lines[:max_pts]
    sentences = re.split(r'(?<=[.!?])\s+', script.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 15][:max_pts]


def safe(text):
    return (str(text)
            .replace("'", "").replace('"', '').replace(':', ' ')
            .replace(',', '').replace('\\', '').replace('%', 'pct')
            .replace('[', '').replace(']', '').strip())


def wrap(text, max_chars=30):
    words, lines, cur = text.split(), [], ''
    for w in words:
        test = f"{cur} {w}".strip()
        if len(test) <= max_chars:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:5]


def build_slide(out, lines, dur, is_title=False, num=0, total=0):
    filters = []
    if is_title:
        yb = H // 2 - 150
        for i, ln in enumerate(lines[:4]):
            s = safe(ln)
            if not s:
                continue
            color = ACCENT_COLOR if i == 0 else TEXT_COLOR
            size  = 64 if i == 0 else 52
            filters.append(
                f"drawtext=text='{s}':fontcolor=0x{color}:fontsize={size}:"
                f"x=(w-text_w)/2:y={yb + i*90}:font={FONT}"
            )
        filters.append(
            f"drawtext=text='IAS Brief':fontcolor=0x{ACCENT_COLOR}:fontsize=42:"
            f"x=(w-text_w)/2:y={H-130}:font={FONT}"
        )
    else:
        yb = H // 2 - len(lines) * 40
        for i, ln in enumerate(lines):
            s = safe(ln)
            if not s:
                continue
            filters.append(
                f"drawtext=text='{s}':fontcolor=0x{TEXT_COLOR}:fontsize=50:"
                f"x=(w-text_w)/2:y={yb + i*75}:font={FONT}"
            )
        filters.append(
            f"drawtext=text='{num}/{total}':fontcolor=0x{DIM_COLOR}:fontsize=36:"
            f"x=(w-text_w)/2:y={H-120}:font={FONT}"
        )
        filters.append(
            f"drawtext=text='IAS Brief':fontcolor=0x{ACCENT_COLOR}40:fontsize=34:"
            f"x=(w-text_w)/2:y={H-78}:font={FONT}"
        )

    vf  = ','.join(filters) if filters else 'null'
    cmd = [
        'ffmpeg', '-y', '-f', 'lavfi',
        '-i', f'color=c=0x{BG_COLOR}:size={W}x{H}:rate={FPS}:duration={dur:.3f}',
        '-vf', vf, '-c:v', 'libx264', '-preset', 'fast',
        '-pix_fmt', 'yuv420p', '-t', f'{dur:.3f}', out
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Slide failed:\n{r.stderr[-400:]}")


def build_video(title, script, audio_path):
    Path('output/slides').mkdir(parents=True, exist_ok=True)

    dur    = get_duration(audio_path)
    points = parse_points(script)
    print(f"Audio: {dur:.1f}s  |  Slides: {len(points)+1}")

    title_dur = min(4.0, dur * 0.15)
    pt_dur    = (dur - title_dur) / max(len(points), 1)

    slides = []

    # Title slide
    tp = 'output/slides/s00_title.mp4'
    build_slide(tp, wrap(title, 26), title_dur, is_title=True)
    slides.append(tp)
    print(f"  Title slide: {title_dur:.1f}s")

    # Content slides
    for i, pt in enumerate(points):
        sp = f'output/slides/s{i+1:02d}.mp4'
        build_slide(sp, wrap(pt, 32), pt_dur, num=i+1, total=len(points))
        slides.append(sp)
        print(f"  Slide {i+1}: {pt_dur:.1f}s — {pt[:50]}...")

    # Write concat list
    clist = 'output/concat.txt'
    with open(clist, 'w') as f:
        for s in slides:
            f.write(f"file '{os.path.abspath(s)}'\n")

    # Concat slides
    merged = 'output/merged.mp4'
    r = subprocess.run([
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
        '-i', clist, '-c', 'copy', merged
    ], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Concat failed:\n{r.stderr[-400:]}")

    # Add audio
    output = 'output/system1_short.mp4'
    r = subprocess.run([
        'ffmpeg', '-y', '-i', merged, '-i', audio_path,
        '-c:v', 'copy', '-c:a', 'aac', '-shortest', output
    ], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Audio merge failed:\n{r.stderr[-400:]}")

    size = os.path.getsize(output)
    print(f"Video ready: {size/1024/1024:.1f} MB → {output}")
    return output


# ── 3. UPLOAD ────────────────────────────────────────────────

def upload(video_path, title, script):
    from yt_upload import upload_video   # existing file, not modified
    desc = (
        f"{title}\n\n"
        f"{script[:400]}\n\n"
        "#UPSC #IASBrief #CurrentAffairs #Shorts #IAS #PIB"
    )
    tags = ['UPSC', 'IAS', 'IAS Brief', 'Current Affairs', 'Shorts', 'PIB']
    return upload_video(video_path, title, desc, tags)


# ── 4. MAIN ──────────────────────────────────────────────────

def main():
    title        = os.environ.get('VIDEO_TITLE', '').strip()
    script       = os.environ.get('VIDEO_SCRIPT', '').strip()
    audio_url    = os.environ.get('AUDIO_URL', '').strip()
    article_link = os.environ.get('ARTICLE_LINK', '').strip()

    print("=" * 50)
    print(f"System1 Short Builder v2")
    print(f"Title:        {title}")
    print(f"Script:       {len(script)} chars")
    print(f"Audio:        {audio_url[:70]}...")
    print(f"Article Link: {article_link[:70] if article_link else 'not provided'}")
    print("=" * 50)

    if not title or not script or not audio_url:
        print("ERROR: VIDEO_TITLE, VIDEO_SCRIPT, AUDIO_URL all required")
        sys.exit(1)

    # ── Full article fetch + script upgrade ──────────────────
    final_script = script   # always falls back to RSS snippet

    if article_link:
        pib_url = resolve_google_news_url(article_link)
        if pib_url:
            print(f"Resolved PIB URL: {pib_url}")
            full_text = fetch_full_article_text(pib_url)
            if full_text:
                better_script = generate_script_from_full_text(title, full_text)
                if better_script:
                    final_script = better_script
                    print("Script upgraded from full article text.")
                else:
                    print("Gemini script generation failed — using original VIDEO_SCRIPT.")
            else:
                print("Full text fetch failed — using original VIDEO_SCRIPT.")
        else:
            print("URL resolution failed — using original VIDEO_SCRIPT.")
    else:
        print("No ARTICLE_LINK — using VIDEO_SCRIPT as-is.")

    # ── Build + upload ───────────────────────────────────────
    audio_path = download_audio(audio_url)
    video_path = build_video(title, final_script, audio_path)
    print("Uploading to YouTube...")
    result = upload(video_path, title, final_script)
    print(f"Upload complete: {result}")


if __name__ == '__main__':
    main()
