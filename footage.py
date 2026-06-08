# ================================================================
#  footage.py — Stock Video Downloader (Pexels + Pixabay)
#  Pexels  : 200 requests/hour free — primary source
#  Pixabay : 100 requests/min  free — fallback
# ================================================================

import os
import random
import requests


PEXELS_API_KEY  = os.environ.get('PEXELS_API_KEY', '')
PIXABAY_API_KEY = os.environ.get('PIXABAY_API_KEY', '')

# Fallback keywords if topic-specific search returns nothing
FALLBACK_KEYWORDS = [
    'India government',
    'India parliament building',
    'India economy',
    'Indian flag',
    'Indian infrastructure'
]


def download_clips(keywords_str, target_duration_sec, output_dir='clips'):
    """
    Search Pexels (+ Pixabay fallback) and download enough clips
    to exceed target_duration_sec.

    keywords_str: comma-separated string from script generator
                  e.g. "India parliament, policy, economy growth"
    Returns: list of dicts [{path, duration}, ...]
    """
    os.makedirs(output_dir, exist_ok=True)

    keyword_list = [k.strip() for k in keywords_str.split(',') if k.strip()]
    if not keyword_list:
        keyword_list = FALLBACK_KEYWORDS

    # Add fallbacks at end in case topic keywords yield nothing
    keyword_list += FALLBACK_KEYWORDS

    all_clips   = []
    total_dur   = 0
    clip_index  = 0
    seen_urls   = set()

    for keyword in keyword_list:
        if total_dur >= target_duration_sec + 15:
            break

        print(f'  🔍 Searching: "{keyword}"')

        videos = _search_pexels(keyword)
        if not videos and PIXABAY_API_KEY:
            videos = _search_pixabay(keyword)

        random.shuffle(videos)

        for video in videos[:3]:
            if total_dur >= target_duration_sec + 15:
                break
            if video['url'] in seen_urls:
                continue

            clip_path = os.path.join(output_dir, f'clip_{clip_index:02d}.mp4')
            try:
                _download_file(video['url'], clip_path)
                all_clips.append({'path': clip_path, 'duration': video['duration']})
                seen_urls.add(video['url'])
                total_dur  += video['duration']
                clip_index += 1
                print(f'     ✅ clip_{clip_index-1:02d}.mp4 ({video["duration"]}s) — total so far: {total_dur:.0f}s')
            except Exception as e:
                print(f'     ⚠️ Download failed: {e}')

    if not all_clips:
        raise Exception('No stock footage downloaded. Check PEXELS_API_KEY and internet access.')

    print(f'  ✅ {len(all_clips)} clips downloaded, {total_dur:.0f}s total coverage')
    return all_clips


# ── Pexels ────────────────────────────────────────────────────────

def _search_pexels(query, per_page=5):
    if not PEXELS_API_KEY:
        return []
    try:
        resp = requests.get(
            'https://api.pexels.com/videos/search',
            headers={'Authorization': PEXELS_API_KEY},
            params={'query': query, 'per_page': per_page,
                    'orientation': 'landscape', 'size': 'medium'},
            timeout=15
        )
        if resp.status_code != 200:
            return []

        results = []
        for v in resp.json().get('videos', []):
            file = _best_pexels_file(v.get('video_files', []))
            if file:
                results.append({'url': file['link'], 'duration': v['duration']})
        return results
    except Exception as e:
        print(f'     ⚠️ Pexels error: {e}')
        return []


def _best_pexels_file(files):
    """Pick the best quality file closest to 720p."""
    hd = [f for f in files if f.get('quality') in ('hd', 'sd') and f.get('link')]
    if not hd:
        return None
    # Closest to 1280×720
    return min(hd, key=lambda f: abs((f.get('width', 0) * f.get('height', 0)) - 921600))


# ── Pixabay ───────────────────────────────────────────────────────

def _search_pixabay(query, per_page=5):
    if not PIXABAY_API_KEY:
        return []
    try:
        resp = requests.get(
            'https://pixabay.com/api/videos/',
            params={'key': PIXABAY_API_KEY, 'q': query, 'per_page': per_page,
                    'video_type': 'film', 'safesearch': 'true'},
            timeout=15
        )
        if resp.status_code != 200:
            return []

        results = []
        for hit in resp.json().get('hits', []):
            vids = hit.get('videos', {})
            file = vids.get('medium') or vids.get('small')
            if file and file.get('url'):
                results.append({'url': file['url'], 'duration': hit['duration']})
        return results
    except Exception as e:
        print(f'     ⚠️ Pixabay error: {e}')
        return []


# ── Downloader ────────────────────────────────────────────────────

def _download_file(url, dest_path, timeout=60):
    resp = requests.get(url, stream=True, timeout=timeout)
    resp.raise_for_status()
    with open(dest_path, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=1024 * 64):
            f.write(chunk)
