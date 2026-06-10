import os
import subprocess

FONT_BOLD    = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
FONT_REGULAR = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BG_COLOR     = '0D1B2A'
ACCENT       = 'F4A261'
TITLE_SECS   = 8


def build_video(script_data, voice_path, output_path='output.mp4', voice_duration=180):
    title      = script_data.get('title', 'UPSC Daily')
    topic      = script_data.get('topic', title)[:55]
    source     = script_data.get('source', 'PIB')
    key_points = script_data.get('key_points') or ['Key facts from today\'s article']

    vf = _build_filter(title, topic, source, key_points, voice_duration)

    cmd = [
        'ffmpeg',
        '-f', 'lavfi',
        '-i', f'color=c=0x{BG_COLOR}:size=1280x720:rate=30:duration={int(voice_duration) + 3}',
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
        raise Exception('Video build failed: ' + result.stderr.decode()[-600:])

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f'  ✅ Video ready: {output_path} ({size_mb:.1f} MB)')
    return output_path


def _build_filter(title, topic, source, key_points, voice_duration):
    f = []
    td = min(TITLE_SECS, voice_duration * 0.15)
    remaining = voice_duration - td
    point_dur = remaining / max(len(key_points), 1)

    # Top accent bar
    f.append(f'drawbox=x=0:y=0:w=1280:h=6:color=0x{ACCENT}:t=1280')

    # Bottom accent bar (static — replaces animated progress bar)
    f.append(f'drawbox=x=0:y=714:w=1280:h=6:color=0x{ACCENT}:t=1280')

    # IAS Brief watermark
    f.append(
        f"drawtext=fontfile={FONT_BOLD}:text='IAS Brief':"
        f"fontsize=28:fontcolor=0x{ACCENT}:x=36:y=22"
    )

    # Source badge
    f.append(
        f"drawtext=fontfile={FONT_BOLD}:text='{_esc(source)}':"
        f"fontsize=24:fontcolor=0x{ACCENT}:x=w-tw-36:y=26"
    )

    # ── TITLE CARD ──────────────────────────────────────────────
    title_lines = _wrap(title, 34)
    y0 = 290 - (len(title_lines) * 60) // 2
    for i, line in enumerate(title_lines[:3]):
        f.append(
            f"drawtext=fontfile={FONT_BOLD}:text='{_esc(line)}':"
            f"fontsize=50:fontcolor=white:"
            f"x=(w-tw)/2:y={y0 + i * 60}:"
            f"enable='between(t\\,0\\,{td:.1f})'"
        )

    # Divider under title
    div_y = y0 + len(title_lines) * 60 + 8
    f.append(
        f"drawbox=x=120:y={div_y}:w=1040:h=2:color=0x{ACCENT}:t=1040:"
        f"enable='between(t\\,0\\,{td:.1f})'"
    )

    # Subtitle
    f.append(
        f"drawtext=fontfile={FONT_REGULAR}:text='Today\\'s UPSC Focus':"
        f"fontsize=28:fontcolor=0x8899AA:"
        f"x=(w-tw)/2:y={div_y + 16}:"
        f"enable='between(t\\,0\\,{td:.1f})'"
    )

    # ── KEY POINTS ───────────────────────────────────────────────
    # Topic label (shown after title card)
    f.append(
        f"drawtext=fontfile={FONT_BOLD}:text='{_esc(topic)}':"
        f"fontsize=26:fontcolor=0x{ACCENT}:"
        f"x=80:y=75:"
        f"enable='between(t\\,{td:.1f}\\,{voice_duration})'"
    )

    # Divider under topic
    f.append(
        f"drawbox=x=80:y=112:w=1120:h=2:color=0x{ACCENT}:t=1120:"
        f"enable='between(t\\,{td:.1f}\\,{voice_duration})'"
    )

    for i, point in enumerate(key_points):
        ts = td + i * point_dur
        te = ts + point_dur

        # Point counter
        f.append(
            f"drawtext=fontfile={FONT_REGULAR}:text='Point {i+1} of {len(key_points)}':"
            f"fontsize=22:fontcolor=0x8899AA:"
            f"x=80:y=148:"
            f"enable='between(t\\,{ts:.1f}\\,{te:.1f})'"
        )

        # Orange bullet bar
        lines = _wrap(point, 40)
        bar_h = min(len(lines), 3) * 62
        f.append(
            f"drawbox=x=60:y=210:w=8:h={bar_h}:color=0x{ACCENT}:t={bar_h}:"
            f"enable='between(t\\,{ts:.1f}\\,{te:.1f})'"
        )

        # Point text
        for j, pline in enumerate(lines[:3]):
            f.append(
                f"drawtext=fontfile={FONT_BOLD}:text='{_esc(pline)}':"
                f"fontsize=44:fontcolor=white:"
                f"x=88:y={210 + j * 62}:"
                f"enable='between(t\\,{ts:.1f}\\,{te:.1f})'"
            )

    # Fade in/out
    f.append('fade=t=in:st=0:d=1.2')
    f.append(f'fade=t=out:st={max(voice_duration - 1.2, 0):.1f}:d=1.2')

    return ','.join(f)


def _wrap(text, max_chars):
    words = str(text).split()
    lines, current = [], ''
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
    return (str(text)
            .replace('\\', '\\\\')
            .replace("'",  '\u2019')
            .replace(':',  '\\:')
            .replace('%',  '\\%')
            .replace('[',  '')
            .replace(']',  '')
            .replace('&',  'and')
            .replace('<',  '')
            .replace('>',  ''))
