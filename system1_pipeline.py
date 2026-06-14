#!/usr/bin/env python3
"""
system1_pipeline.py — v3
Triggered by repository_dispatch (event_type: system1_video).
Env vars: VIDEO_TITLE, ARTICLE_LINK

Flow:
  1. curl -L resolves Google News URL → direct PIB URL
  2. Jina fetches full PIB article text
  3. Gemini generates structured 5-scene video package
  4. Kokoro TTS generates per-scene audio (af_heart, 1.2x speed)
  5. Pexels fetches per-scene background image
  6. FFmpeg builds per-scene clips (image bg + text overlay + audio)
  7. Clips concatenated → uploaded to @iasbrief
"""

import os, sys, json, re, subprocess, requests, time
from pathlib import Path
import numpy as np
import soundfile as sf

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

# ── CONSTANTS ────────────────────────────────────────────────

BG_COLOR     = '0D1B2A'
ACCENT_COLOR = 'F4A261'
TEXT_COLOR   = 'FFFFFF'
W, H, FPS    = 1080, 1920, 30
FONT         = 'Sans'

GEMINI_KEY   = os.environ.get('GEMINI_API_KEY', '')
GEMINI_MODEL = 'gemini-3.5-flash'
GEMINI_URL   = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent'
PEXELS_KEY   = os.environ.get('PEXELS_API_KEY', '')

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Prompt is defined as a module-level constant so it can be reviewed
# without touching pipeline logic.
GEMINI_PROMPT = """\
You are an elite short-form news video producer and UPSC educator.
Convert this PIB press release into a faceless YouTube Shorts video package.

Return valid JSON only. No text before or after the JSON block.

{{
  "title": "Max 8 words. Fact-first. No clickbait.",
  "description": "3 sentences. What happened, why it matters, UPSC angle.",
  "hashtags": ["UPSC", "IASBrief", "CurrentAffairs", "Shorts"],
  "scenes": [
    {{
      "scene_number": 1,
      "narration": "Spoken narration for this scene. Conversational English. Explain clearly — assume the viewer knows nothing about this topic. No jargon without explanation. No emojis. No markdown.",
      "onscreen_text": "Max 6 words. One standalone fact. Complements narration, does not repeat it.",
      "search_keywords": ["3 word Pexels search query relevant to this scene"]
    }}
  ]
}}

RULES:
- Exactly 5 scenes
- Total narration across all scenes: 170-190 words
- Scene 1: open with the single most important fact — no throat-clearing
- Scene 5: close with UPSC angle — GS paper tag (GS1/GS2/GS3/GS4), scheme name, or constitutional article if applicable
- Narration flows continuously — each scene picks up where the last ended
- Each scene narration: 30-40 words
- No political bias. No clickbait. Only facts from the article.
- onscreen_text must complement narration, not repeat it word for word

ARTICLE TITLE: {title}

ARTICLE TEXT:
{article_text}"""


# ── 0. URL RESOLUTION ────────────────────────────────────────

def resolve_google_news_url(google_url):
    """
    Use curl -L to follow Google News redirect chain.
    Python requests cannot follow Google's JS-based redirects;
    curl handles the full HTTP redirect chain reliably on GitHub runners.
    """
    print(f"Resolving: {google_url[:80]}...")
    try:
        result = subprocess.run([
            'curl', '-L', '-s', '-o', '/dev/null', '-w', '%{url_effective}',
            '-A', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            '--max-redirs', '10',
            '--connect-timeout', '15',
            google_url
        ], capture_output=True, text=True, timeout=25)

        final_url = result.stdout.strip()
        if 'pib.gov.in' in final_url:
            print(f"Resolved: {final_url}")
            return final_url
        print(f"curl landed on non-PIB URL: {final_url[:80]}")
    except Exception as e:
        print(f"curl failed: {e}")

    # Fallback: requests + HTML parse
    try:
        resp = requests.get(google_url, headers=BROWSER_HEADERS,
                            allow_redirects=True, timeout=15)
        if 'pib.gov.in' in resp.url:
            return resp.url
        html = resp.text
        m = re.search(r'href=["\']([^"\']*pib\.gov\.in[^"\']*)["\']', html)
        if m:
            return m.group(1)
        if BS4_AVAILABLE:
            from bs4 import BeautifulSoup
            for a in BeautifulSoup(html, 'html.parser').find_all('a', href=True):
                if 'pib.gov.in' in a['href']:
                    return a['href']
    except Exception as e:
        print(f"requests fallback failed: {e}")

    print("URL resolution failed — no PIB URL found")
    return None


# ── 1. FULL ARTICLE FETCH ────────────────────────────────────

def fetch_full_article_text(pib_url):
    """
    Jina primary: confirmed working for PIB (HTTP 200, ~7500 chars).
    Direct fetch fallback: GitHub runner IPs bypass PIB Cloudflare.
    """
    try:
        jina_url = f'https://r.jina.ai/{pib_url}'
        print(f"Jina fetch: {jina_url[:80]}...")
        resp = requests.get(jina_url, timeout=30)
        if resp.status_code == 200 and len(resp.text) > 500:
            print(f"Jina OK: {len(resp.text):,} chars")
            return resp.text
        print(f"Jina: {resp.status_code} / {len(resp.text)} chars")
    except Exception as e:
        print(f"Jina failed: {e}")

    try:
        print(f"Direct fetch: {pib_url[:80]}...")
        resp = requests.get(pib_url, headers=BROWSER_HEADERS, timeout=20)
        if resp.status_code == 200 and len(resp.text) > 500:
            print(f"Direct fetch OK: {len(resp.text):,} chars")
            return resp.text
    except Exception as e:
        print(f"Direct fetch failed: {e}")

    return None


# ── 2. GEMINI VIDEO PACKAGE ──────────────────────────────────

def generate_video_package(title, article_text):
    """
    Single Gemini call produces the full 5-scene structure:
    title, description, hashtags, and per-scene narration + onscreen_text + search_keywords.
    All downstream steps (audio, images, video) derive from this one output.
    """
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")

    prompt = GEMINI_PROMPT.format(
        title=title,
        article_text=article_text[:4000]
    )

    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'temperature': 0.4, 'maxOutputTokens': 1500}
    }

    for attempt in range(3):
        try:
            resp = requests.post(
                f'{GEMINI_URL}?key={GEMINI_KEY}',
                json=payload, timeout=45
            )
            if resp.status_code == 200:
                raw = resp.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                raw = re.sub(r'^```(?:json)?\s*', '', raw)
                raw = re.sub(r'\s*```$', '', raw)
                package = json.loads(raw)
                scenes = package.get('scenes', [])
                if len(scenes) >= 3:
                    print(f"Gemini OK: {len(scenes)} scenes — {package.get('title', '')[:60]}")
                    return package
                print(f"Gemini: too few scenes ({len(scenes)}) — retrying")
            elif resp.status_code == 503:
                wait = 20 * (attempt + 1)
                print(f"Gemini 503 — retry in {wait}s")
                time.sleep(wait)
            else:
                print(f"Gemini {resp.status_code}: {resp.text[:200]}")
                break
        except json.JSONDecodeError as e:
            print(f"JSON parse failed (attempt {attempt+1}): {e}")
            time.sleep(10)
        except Exception as e:
            print(f"Gemini attempt {attempt+1}: {e}")
            time.sleep(10)

    return None


# ── 3. KOKORO AUDIO ──────────────────────────────────────────

def generate_scene_audio(narration, output_path, speed=1.2):
    """
    Generates audio for one scene narration.
    Speed 1.2 targets ~65s total for 170-190 word scripts.
    Voice af_heart matches System 2 (same repo, same Kokoro install).
    """
    from kokoro import KPipeline

    pipeline = KPipeline(lang_code='a')  # 'a' = American English
    chunks = []

    for _, _, audio in pipeline(narration, voice='af_heart', speed=speed):
        if audio is not None and len(audio) > 0:
            chunks.append(audio)

    if not chunks:
        raise RuntimeError(f"Kokoro produced no audio for: {narration[:60]}")

    audio_data = np.concatenate(chunks)
    sf.write(output_path, audio_data, 24000)
    print(f"Audio: {os.path.getsize(output_path):,} bytes → {output_path}")
    return output_path


def get_duration(path):
    result = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', path],
        capture_output=True, text=True, check=True
    )
    for s in json.loads(result.stdout).get('streams', []):
        if 'duration' in s:
            return float(s['duration'])
    raise RuntimeError(f"Cannot read duration: {path}")


# ── 4. PEXELS IMAGE FETCH ────────────────────────────────────

def fetch_pexels_image(keywords, scene_num):
    """
    Fetches portrait-orientation image for scene background.
    Falls back to solid dark navy if Pexels fails or key is missing.
    Portrait orientation = 9:16, correct for YouTube Shorts.
    """
    if not PEXELS_KEY:
        print(f"No PEXELS_API_KEY — solid background for scene {scene_num}")
        return None

    query = ' '.join(keywords) if isinstance(keywords, list) else str(keywords)
    try:
        resp = requests.get(
            'https://api.pexels.com/v1/search',
            headers={'Authorization': PEXELS_KEY},
            params={'query': query, 'per_page': 3, 'orientation': 'portrait'},
            timeout=15
        )
        if resp.status_code == 200:
            photos = resp.json().get('photos', [])
            if photos:
                img_url = photos[0]['src']['large2x']
                img_resp = requests.get(img_url, timeout=30)
                path = f'output/scenes/bg_{scene_num:02d}.jpg'
                with open(path, 'wb') as f:
                    f.write(img_resp.content)
                print(f"Pexels scene {scene_num}: '{query}' → {path}")
                return path
        print(f"Pexels scene {scene_num}: {resp.status_code} — solid background")
    except Exception as e:
        print(f"Pexels scene {scene_num} failed: {e}")

    return None


# ── 5. VIDEO BUILDER ─────────────────────────────────────────

def safe_text(text):
    """Strip characters that break FFmpeg drawtext."""
    return (str(text)
            .replace("'", "").replace('"', '').replace(':', ' ')
            .replace('\\', '').replace('%', 'pct')
            .replace('[', '').replace(']', '')
            .replace('{', '').replace('}', '')
            .strip())


def build_scene_clip(scene_num, onscreen_text, audio_path, bg_image_path, output_path):
    """
    Builds one scene clip:
    - Background: Pexels image (scaled+cropped to 1080x1920) or solid navy
    - Bottom bar: semi-transparent dark overlay with onscreen_text
    - Watermark: IAS Brief in accent color
    - Audio: scene narration from Kokoro
    Duration is driven by actual audio length, not a fixed value.
    """
    duration = get_duration(audio_path)
    text = safe_text(onscreen_text)

    # Text overlay: dark bar at bottom + centered text + watermark
    overlay = (
        f"drawbox=x=0:y={H-300}:w={W}:h=300:color=black@0.70:t=fill,"
        f"drawtext=text='{text}':fontcolor=0x{TEXT_COLOR}:fontsize=46:"
        f"x=(w-text_w)/2:y={H-220}:font={FONT},"
        f"drawtext=text='IAS Brief':fontcolor=0x{ACCENT_COLOR}:fontsize=36:"
        f"x=(w-text_w)/2:y={H-68}:font={FONT}"
    )

    if bg_image_path and os.path.exists(bg_image_path):
        vf = (
            f"scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},"
            f"{overlay}"
        )
        cmd = [
            'ffmpeg', '-y',
            '-loop', '1', '-i', bg_image_path,
            '-i', audio_path,
            '-vf', vf,
            '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-shortest', '-t', f'{duration:.3f}',
            output_path
        ]
    else:
        # Solid color fallback
        vf = f"{overlay}"
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', f'color=c=0x{BG_COLOR}:size={W}x{H}:rate={FPS}:duration={duration:.3f}',
            '-i', audio_path,
            '-vf', vf,
            '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-shortest',
            output_path
        ]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Scene {scene_num} build failed:\n{r.stderr[-400:]}")
    print(f"Scene {scene_num}: {duration:.1f}s → {output_path}")
    return output_path


def concatenate_clips(clip_paths, output_path):
    clist = 'output/concat.txt'
    with open(clist, 'w') as f:
        for p in clip_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    r = subprocess.run([
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
        '-i', clist, '-c', 'copy', output_path
    ], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Concat failed:\n{r.stderr[-400:]}")

    size = os.path.getsize(output_path)
    print(f"Final video: {size/1024/1024:.1f} MB → {output_path}")
    return output_path


# ── 6. UPLOAD ────────────────────────────────────────────────

def upload(video_path, package):
    from yt_upload import upload_video
    title       = package.get('title', 'UPSC Current Affairs')
    description = (
        f"{package.get('description', '')}\n\n"
        + ' '.join(f"#{tag}" for tag in package.get('hashtags', []))
    )
    tags = package.get('hashtags', ['UPSC', 'IAS', 'CurrentAffairs', 'Shorts'])
    return upload_video(video_path, title, description, tags)


# ── 7. MAIN ──────────────────────────────────────────────────

def main():
    title        = os.environ.get('VIDEO_TITLE', '').strip()
    article_link = os.environ.get('ARTICLE_LINK', '').strip()

    print("=" * 50)
    print(f"System1 Short Builder v3")
    print(f"Title:        {title}")
    print(f"Article Link: {article_link[:80]}")
    print("=" * 50)

    if not title or not article_link:
        print("ERROR: VIDEO_TITLE and ARTICLE_LINK are both required")
        sys.exit(1)

    Path('output/scenes').mkdir(parents=True, exist_ok=True)

    # ── Step 1: Resolve URL ──────────────────────────────────
    pib_url = resolve_google_news_url(article_link)
    if not pib_url:
        print("FATAL: Could not resolve PIB URL — aborting")
        sys.exit(1)

    # ── Step 2: Fetch article text ───────────────────────────
    article_text = fetch_full_article_text(pib_url)
    if not article_text:
        print("FATAL: Could not fetch article text — aborting")
        sys.exit(1)
    print(f"Article: {len(article_text):,} chars")

    # ── Step 3: Generate video package ──────────────────────
    package = generate_video_package(title, article_text)
    if not package:
        print("FATAL: Gemini failed — aborting")
        sys.exit(1)

    scenes = package['scenes']
    print(f"\nVideo title: {package.get('title', '')}")
    print(f"Scenes: {len(scenes)}\n")

    # ── Steps 4-5: Per-scene audio + image + clip ────────────
    clip_paths = []
    for scene in scenes:
        n            = scene['scene_number']
        narration    = scene.get('narration', '')
        onscreen     = scene.get('onscreen_text', '')
        keywords     = scene.get('search_keywords', ['India government news'])

        print(f"── Scene {n} ───────────────────────────────")
        print(f"  Narration ({len(narration.split())}w): {narration[:70]}...")
        print(f"  Onscreen: {onscreen}")

        audio_path = f'output/scenes/audio_{n:02d}.wav'
        generate_scene_audio(narration, audio_path, speed=1.2)

        bg_path   = fetch_pexels_image(keywords, n)
        clip_path = f'output/scenes/clip_{n:02d}.mp4'
        build_scene_clip(n, onscreen, audio_path, bg_path, clip_path)
        clip_paths.append(clip_path)

    # ── Step 6: Concatenate ──────────────────────────────────
    print("\n── Concatenating ───────────────────────────")
    final_video = 'output/system1_short.mp4'
    concatenate_clips(clip_paths, final_video)

    total_duration = sum(get_duration(p) for p in clip_paths)
    print(f"Total duration: {total_duration:.1f}s")

    # ── Step 7: Upload ───────────────────────────────────────
    print("\nUploading to YouTube...")
    result = upload(final_video, package)
    print(f"Upload complete: {result}")


if __name__ == '__main__':
    main()
