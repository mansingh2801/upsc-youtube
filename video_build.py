# ================================================================
#  video_build.py — Slideshow-style YouTube Shorts builder
#  Format : 1080x1920 vertical (Shorts)
#  Style  : Title card → one key point per slide → outro
#  No enable expressions — each slide is a separate clip
# ================================================================

import os
import subprocess

FONT_BOLD    = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
FONT_REGULAR = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
W, H         = 1080, 1920
BG           = '0x0D1B2A'
ACCENT       = '0xF4A261'
WHITE        = '0xFFFFFF'
GREY         = '0x8899AA'
TITLE_DUR    = 5


def build_video(script_data, voice_path,
                output_path='output.mp4', voice_duration=50):

    title      = script_data.get('title', 'UPSC Daily')
    topic      = script_data.get('topic', title)[:50]
    source     = script_data.get('source', 'PIB')
    key_points = script_data.get('key_points') or ['Key UPSC facts']

    remaining  = max(voice_duration - TITLE_DUR, 10)
    point_dur  = remaining / len(key_points)

    slide_clips = []

    # ── Title slide ───────────────────────────────────────────────
    title_clip = _make_title_slide(title, source, TITLE_DUR)
    slide_clips.append(title_clip)

    # ── Key point slides ──────────────────────────────────────────
    for i, point in enumerate(key_points):
        clip = _make_point_slide(
            point       = point,
            topic       = topic,
            source      = source,
            index       = i + 1,
            total       = len(key_points),
            duration    = point_dur
        )
        slide_clips.append(clip)

    # ── Concatenate slides ────────────────────────────────────────
    concat_path = 'slides_concat.mp4'
    _concat(slide_clips, concat_path)

    # ── Add voiceover + fade ──────────────────────────────────────
    _add_audio(concat_path, voice_path, output_path, voice_duration)

    # ── Cleanup temp clips ────────────────────────────────────────
    for c in slide_clips + [concat_path]:
        try: os.remove(c)
        except: pass

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f'  ✅ Shorts video ready: {output_path} ({size_mb:.1f} MB)')
    return output_path


# ── Slide makers ─────────────────────────────────────────────────

def _make_title_slide(title, source, duration):
    out  = 'slide_title.mp4'
    lines = _wrap(title, 22)[:3]
    f    = []

    # Accent bars
    f.append(f'drawbox=x=0:y=0:w={W}:h=8:color={ACCENT}:t=fill')
    f.append(f'drawbox=x=0:y={H-8}:w={W}:h=8:color={ACCENT}:t=fill')

    # IAS Brief branding
    f.append(
        f"drawtext=fontfile={FONT_BOLD}:text='IAS Brief':"
        f"fontsize=52:fontcolor={ACCENT}:x=(w-tw)/2:y=120"
    )

    # Divider
    f.append(f'drawbox=x=120:y=210:w=840:h=3:color={ACCENT}:t=fill')

    # Source badge
    f.append(
        f"drawtext=fontfile={FONT_BOLD}:text='[ {_e(source)} ]':"
        f"fontsize=36:fontcolor={GREY}:x=(w-tw)/2:y=240"
    )

    # Title lines
    y0 = 820 - (len(lines) * 110) // 2
    for i, line in enumerate(lines):
        f.append(
            f"drawtext=fontfile={FONT_BOLD}:text='{_e(line)}':"
            f"fontsize=72:fontcolor={WHITE}:"
            f"x=(w-tw)/2:y={y0 + i * 110}"
        )

    # "Today's UPSC Focus" label
    f.append(
        f"drawtext=fontfile={FONT_REGULAR}:text='Today\\'s UPSC Focus':"
        f"fontsize=38:fontcolor={GREY}:x=(w-tw)/2:y=1150"
    )

    f.append('fade=t=in:st=0:d=0.5')

    return _render_slide('\n'.join(f), duration, out)


def _make_point_slide(point, topic, source, index, total, duration):
    out   = f'slide_{index}.mp4'
    lines = _wrap(point, 20)[:3]
    f     = []

    # Accent bars
    f.append(f'drawbox=x=0:y=0:w={W}:h=8:color={ACCENT}:t=fill')
    f.append(f'drawbox=x=0:y={H-8}:w={W}:h=8:color={ACCENT}:t=fill')

    # IAS Brief top left
    f.append(
        f"drawtext=fontfile={FONT_BOLD}:text='IAS Brief':"
        f"fontsize=36:fontcolor={ACCENT}:x=50:y=30"
    )

    # Source top right
    f.append(
        f"drawtext=fontfile={FONT_BOLD}:text='{_e(source)}':"
        f"fontsize=34:fontcolor={ACCENT}:x=w-tw-50:y=34"
    )

    # Topic label
    f.append(
        f"drawtext=fontfile={FONT_REGULAR}:text='{_e(topic)}':"
        f"fontsize=34:fontcolor={GREY}:x=(w-tw)/2:y=110"
    )

    # Divider
    f.append(f'drawbox=x=80:y=162:w=920:h=2:color={ACCENT}:t=fill')

    # Point counter badge
    f.append(
        f"drawtext=fontfile={FONT_BOLD}:text='Point {index} of {total}':"
        f"fontsize=38:fontcolor={ACCENT}:x=(w-tw)/2:y=700"
    )

    # Orange accent bar left of text
    bar_h = len(lines) * 100
    f.append(
        f'drawbox=x=60:y=820:w=10:h={bar_h}:color={ACCENT}:t=fill'
    )

    # Point text lines
    for i, line in enumerate(lines):
        f.append(
            f"drawtext=fontfile={FONT_BOLD}:text='{_e(line)}':"
            f"fontsize=68:fontcolor={WHITE}:"
            f"x=90:y={820 + i * 100}"
        )

    f.append('fade=t=in:st=0:d=0.3')

    return _render_slide('\n'.join(f), duration, out)


def _render_slide(vf_multiline, duration, output):
    """Generate a silent video clip from a background color + filters."""
    vf = vf_multiline.replace('\n', ',')

    cmd = [
        'ffmpeg',
        '-f', 'lavfi',
        '-i', f'color=c=0x0D1B2A:size={W}x{H}:rate=30:duration={duration:.2f}',
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
        '-an',
        '-y', output
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise Exception(f'Slide render failed ({output}):\n' +
                        result.stderr.decode()[-400:])
    return output


def _concat(clips, output):
    """Concatenate silent slide clips."""
    list_file = 'slide_list.txt'
    with open(list_file, 'w') as f:
        for c in clips:
            f.write(f"file '{os.path.abspath(c)}'\n")

    cmd = [
        'ffmpeg',
        '-f', 'concat', '-safe', '0', '-i', list_file,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
        '-an',
        '-y', output
    ]
    result = subprocess.run(cmd, capture_output=True)
    try: os.remove(list_file)
    except: pass
    if result.returncode != 0:
        raise Exception('Concat failed:\n' + result.stderr.decode()[-400:])


def _add_audio(video_path, audio_path, output, voice_duration):
    """Merge silent slideshow with voiceover, add fade in/out."""
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-i', audio_path,
        '-vf', (
            f'fade=t=in:st=0:d=0.8,'
            f'fade=t=out:st={max(voice_duration - 0.8, 0):.1f}:d=0.8'
        ),
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
        '-c:a', 'aac', '-b:a', '128k',
        '-map', '0:v', '-map', '1:a',
        '-shortest',
        '-movflags', '+faststart',
        '-y', output
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise Exception('Audio merge failed:\n' + result.stderr.decode()[-400:])


# ── Helpers ───────────────────────────────────────────────────────

def _wrap(text, max_chars):
    words = str(text).split()
    lines, current = [], ''
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = (current + ' ' + word).strip()
        else:
            if current: lines.append(current)
            current = word
    if current: lines.append(current)
    return lines or [str(text)[:max_chars]]


def _e(text):
    return (str(text)
            .replace('\\', '\\\\')
            .replace("'",  '\u2019')
            .replace(':',  '\\:')
            .replace('%',  '\\%')
            .replace('[',  '').replace(']', '')
            .replace('&',  'and')
            .replace('<',  '').replace('>',  ''))
