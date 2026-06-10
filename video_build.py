# ================================================================
#  video_build.py — Dark Background Video Builder
#  Professional text-overlay style (no stock footage needed)
#  Design: Dark navy bg + orange accents + timed key points
# ================================================================

import os
import subprocess

FONT_BOLD    = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
FONT_REGULAR = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BG_COLOR     = '0D1B2A'   # dark navy
ACCENT       = 'F4A261'   # warm orange
TITLE_SECS   = 8          # seconds for title card


def build_video(script_data, voice_path, output_path='output.mp4', voice_duration=180):
    """
    Build a professional dark-background UPSC video.
    No stock footage — clean text overlays on dark background.
    """
    title      = script_data.get('title', 'UPSC Daily')
    topic      = script_data.get('topic', title)[:55]
    source     = script_data.get('source', 'PIB')
    key_points = script_data.get('key_points', [])

    if not key_points:
        key_points = ['Key facts from today\'s article']

    vf = _build_filter(title, topic, source, key_points, voice_duration)

    cmd = [
        'ffmpeg',
        '-f', 'lavfi',
        '-i', f'color=c=#{BG_COLOR}:size=1280x720:rate=30:duration={voice_duration + 2}',
        '-i', voice_path,
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
        '-c:a', 'aac', '-b:a', '128k',
        '-map', '0:v', '-map', '1:a',
        '-shortest',
        '-movflags', '+faststart',
        '-y', output_path
    ]

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise Exception('Video build failed: ' + result.stderr.decode()[-400:])

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f'  ✅ Video ready: {output_path} ({size_mb:.1f} MB)')
    return output_path


def _build_filter(title, topic, source, key_points, voice_duration):
    f = []

    td = min(TITLE_SECS, voice_duration * 0.15)   # title card duration
    remaining  = voice_duration - td
    point_dur  = remaining / len(key_points)

    # ── Top accent bar ────────────────────────────────────────────
    f.append(f'drawbox=x=0:y=0:w=iw:h=6:color=#{ACCENT}@1:t=fill')

    # ── Progress bar (grows left to right, orange) ────────────────
    f.append(
        f"drawbox=x=0:y=714:w='iw*t/{voice_duration:.0f}':h=6"
        f":color=#{ACCENT}@1:t=fill"
    )

    # ── IAS Brief watermark (always visible) ──────────────────────
    f.append(
        f"drawtext=fontfile={FONT_BOLD}:text='IAS Brief':"
        f"fontsize=28:fontcolor=#{ACCENT}:x=36:y=22"
    )

    # ── Source badge top right ────────────────────────────────────
    f.append(
        f"drawtext=fontfile={FONT_BOLD}:text='[ {_esc(source)} ]':"
        f"fontsize=24:fontcolor=#{ACCENT}:x=w-tw-36:y=26"
    )

    # ════════════════════════════════════════════════════════════
    # TITLE CARD (0 → td seconds)
    # ════════════════════════════════════════════════════════════

    title_lines = _wrap(title, 34)
    y0 = 280 - (len(title_lines) * 58) // 2
    for i, line in enumerate(title_lines[:3]):
        f.append(
            f"drawtext=fontfile={FONT_BOLD}:text='{_esc(line)}':"
            f"fontsize=50:fontcolor=white:"
            f"x=(w-tw)/2:y={y0 + i*58}:"
            f"enable='between(t,0,{td:.1f})'"
        )

    # Divider line below title
    f.append(
        f"drawbox=x=120:y={y0 + len(title_lines)*58 + 10}:w=1040:h=2"
        f":color=#{ACCENT}@0.7:t=fill:enable='between(t,0,{td:.1f})'"
    )

    # Subtitle
    f.append(
        f"drawtext=fontfile={FONT_REGULAR}:text='Today\\'s UPSC Focus':"
        f"fontsize=28:fontcolor=8899AA:"
        f"x=(w-tw)/2:y={y0 + len(title_lines)*58 + 24}:"
        f"enable='between(t,0,{td:.1f})'"
    )

    # ════════════════════════════════════════════════════════════
    # KEY POINTS SECTION (td → end)
    # ════════════════════════════════════════════════════════════

    # Topic label
    f.append(
        f"drawtext=fontfile={FONT_BOLD}:text='{_esc(topic)}':"
        f"fontsize=26:fontcolor=#{ACCENT}:"
        f"x=80:y=75:"
        f"enable='between(t,{td:.1f},{voice_duration})'"
    )

    # Divider under topic
    f.append(
        f"drawbox=x=80:y=112:w=1120:h=2:color=#{ACCENT}@0.35:t=fill:"
        f"enable='between(t,{td:.1f},{voice_duration})'"
    )

    for i, point in enumerate(key_points):
        ts = td + i * point_dur
        te = ts + point_dur

        # Point counter
        f.append(
            f"drawtext=fontfile={FONT_REGULAR}:"
            f"text='Point {i+1} of {len(key_points)}':"
            f"fontsize=22:fontcolor=8899AA:"
            f"x=80:y=148:"
            f"enable='between(t,{ts:.1f},{te:.1f})'"
        )

        # Orange bullet bar
        lines = _wrap(point, 40)
        bar_h = min(len(lines), 3) * 62
        f.append(
            f"drawbox=x=60:y=210:w=8:h={bar_h}"
            f":color=#{ACCENT}:t=fill:"
            f"enable='between(t,{ts:.1f},{te:.1f})'"
        )

        # Point text lines
        for j, pline in enumerate(lines[:3]):
            f.append(
                f"drawtext=fontfile={FONT_BOLD}:text='{_esc(pline)}':"
                f"fontsize=44:fontcolor=white:"
                f"x=88:y={210 + j*62}:"
                f"enable='between(t,{ts:.1f},{te:.1f})'"
            )

    # ── Fade in / out ─────────────────────────────────────────────
    f.append('fade=t=in:st=0:d=1.2')
    f.append(f'fade=t=out:st={voice_duration - 1.2:.1f}:d=1.2')

    return ','.join(f)


def _wrap(text, max_chars):
    """Word-wrap text into lines of max_chars."""
    words   = str(text).split()
    lines   = []
    current = ''
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = (current + ' ' + word).strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [str(text)[:max_chars]]


def _esc(text):
    """Escape special characters for FFmpeg drawtext."""
    return (str(text)
            .replace('\\', '\\\\')
            .replace("'",  '\u2019')
            .replace(':',  '\\:')
            .replace('%',  '\\%')
            .replace('[',  '\\[')
            .replace(']',  '\\]')
            .replace('&',  'and')
            .replace('<',  '')
            .replace('>',  ''))
