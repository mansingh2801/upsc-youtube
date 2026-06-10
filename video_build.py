import os
import subprocess

FONT_BOLD    = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
FONT_REGULAR = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BG_COLOR     = '0x0D1B2A'
ACCENT       = '0xF4A261'


def build_video(script_data, voice_path, output_path='output.mp4', voice_duration=180):
    title      = script_data.get('title', 'UPSC Daily')[:60]
    topic      = script_data.get('topic', title)[:55]
    source     = script_data.get('source', 'PIB')
    key_points = script_data.get('key_points') or ['Key facts from today']

    filters = []

    # Top + bottom accent bars
    filters.append(f'drawbox=x=0:y=0:w=1280:h=6:color={ACCENT}:t=fill')
    filters.append(f'drawbox=x=0:y=714:w=1280:h=6:color={ACCENT}:t=fill')

    # IAS Brief watermark
    filters.append(
        f"drawtext=fontfile={FONT_BOLD}:"
        f"text='IAS Brief':fontsize=26:fontcolor={ACCENT}:x=36:y=20"
    )

    # Source badge top right
    filters.append(
        f"drawtext=fontfile={FONT_BOLD}:"
        f"text='{_e(source)}':fontsize=24:fontcolor={ACCENT}:x=w-tw-36:y=24"
    )

    # Title (wrapped, up to 2 lines)
    title_lines = _wrap(title, 42)[:2]
    for i, line in enumerate(title_lines):
        filters.append(
            f"drawtext=fontfile={FONT_BOLD}:"
            f"text='{_e(line)}':fontsize=42:fontcolor=white:"
            f"x=(w-tw)/2:y={70 + i * 52}"
        )

    # Divider
    div_y = 70 + len(title_lines) * 52 + 8
    filters.append(
        f'drawbox=x=80:y={div_y}:w=1120:h=2:color={ACCENT}:t=fill'
    )

    # Topic label
    filters.append(
        f"drawtext=fontfile={FONT_REGULAR}:"
        f"text='{_e(topic)}':fontsize=22:fontcolor={ACCENT}:"
        f"x=80:y={div_y + 10}"
    )

    # Key points — all visible, stacked
    kp_start_y = div_y + 44
    for i, point in enumerate(key_points[:5]):
        lines = _wrap(point, 48)[:2]
        y = kp_start_y + i * 96
        # Bullet dot
        filters.append(
            f'drawbox=x=80:y={y + 10}:w=10:h=10:color={ACCENT}:t=fill'
        )
        for j, line in enumerate(lines):
            filters.append(
                f"drawtext=fontfile={FONT_BOLD}:"
                f"text='{_e(line)}':fontsize=30:fontcolor=white:"
                f"x=104:y={y + j * 36}"
            )

    # Fade in / out
    filters.append('fade=t=in:st=0:d=1.2')
    filters.append(f'fade=t=out:st={max(voice_duration - 1.2, 0):.1f}:d=1.2')

    vf = ','.join(filters)

    cmd = [
        'ffmpeg',
        '-f', 'lavfi',
        '-i', f'color=c=0x0D1B2A:size=1280x720:rate=30:duration={int(voice_duration) + 3}',
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
        raise Exception('FFmpeg failed:\n' + result.stderr.decode()[-500:])

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f'  ✅ Video ready: {output_path} ({size_mb:.1f} MB)')
    return output_path


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


def _e(text):
    """Escape text for FFmpeg drawtext."""
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
