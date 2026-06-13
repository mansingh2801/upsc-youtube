#!/usr/bin/env python3
"""
system1_pipeline.py
Triggered by repository_dispatch (event_type: system1_video).
Receives VIDEO_TITLE, VIDEO_SCRIPT, AUDIO_URL via env vars.
Downloads Sarvam audio → builds slideshow Short → uploads to @iasbrief.
Does NOT touch any System 2 file.
"""

import os, sys, json, re, subprocess, requests
from pathlib import Path

# Visual constants — match System 2 style exactly
BG_COLOR     = '0D1B2A'
ACCENT_COLOR = 'F4A261'
TEXT_COLOR   = 'FFFFFF'
DIM_COLOR    = 'AAAAAA'
W, H, FPS    = 1080, 1920, 30
FONT         = 'Sans'


# ── 1. DOWNLOAD AUDIO ───────────────────────────────────────

def download_audio(url: str, dest: str = 'output/voice.wav') -> str:
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


# ── 2. VIDEO BUILDER ────────────────────────────────────────

def get_duration(path: str) -> float:
    result = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', path],
        capture_output=True, text=True, check=True
    )
    for s in json.loads(result.stdout).get('streams', []):
        if 'duration' in s:
            return float(s['duration'])
    raise RuntimeError("Cannot read audio duration")


def parse_points(script: str, max_pts: int = 5) -> list:
    lines = [l.strip() for l in script.split('\n') if len(l.strip()) > 15]
    if len(lines) >= 3:
        return lines[:max_pts]
    sentences = re.split(r'(?<=[.!?])\s+', script.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 15][:max_pts]


def safe(text: str) -> str:
    return (str(text)
            .replace("'", "").replace('"', '').replace(':', ' ')
            .replace(',', '').replace('\\', '').replace('%', 'pct')
            .replace('[', '').replace(']', '').strip())


def wrap(text: str, max_chars: int = 30) -> list:
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


def build_slide(out: str, lines: list, dur: float,
                is_title=False, num=0, total=0):
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


def build_video(title: str, script: str, audio_path: str) -> str:
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
        build_slide(sp, wrap(pt, 32), pt_dur,
                    num=i+1, total=len(points))
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


# ── 3. UPLOAD ───────────────────────────────────────────────

def upload(video_path: str, title: str, script: str) -> str:
    from yt_upload import upload_video   # existing file, not modified
    desc = (
        f"{title}\n\n"
        f"{script[:400]}\n\n"
        "#UPSC #IASBrief #CurrentAffairs #Shorts #IAS #PIB"
    )
    tags = ['UPSC', 'IAS', 'IAS Brief', 'Current Affairs', 'Shorts', 'PIB']
    return upload_video(video_path, title, desc, tags)


# ── 4. MAIN ─────────────────────────────────────────────────

def main():
    title     = os.environ.get('VIDEO_TITLE', '').strip()
    script    = os.environ.get('VIDEO_SCRIPT', '').strip()
    audio_url = os.environ.get('AUDIO_URL', '').strip()

    print("=" * 50)
    print(f"System1 Short Builder")
    print(f"Title:  {title}")
    print(f"Script: {len(script)} chars")
    print(f"Audio:  {audio_url[:70]}...")
    print("=" * 50)

    if not title or not script or not audio_url:
        print("ERROR: VIDEO_TITLE, VIDEO_SCRIPT, AUDIO_URL all required")
        sys.exit(1)

    audio_path = download_audio(audio_url)
    video_path = build_video(title, script, audio_path)
    print("Uploading to YouTube...")
    result = upload(video_path, title, script)
    print(f"Upload complete: {result}")


if __name__ == '__main__':
    main()
