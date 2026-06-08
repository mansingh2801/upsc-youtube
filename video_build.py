# ================================================================
#  video_build.py — FFmpeg Video Builder
#  Steps:
#   1. Normalize all clips → 1280×720, 30fps, no audio
#   2. Concatenate (loop if needed to cover voice duration)
#   3. Merge with voiceover audio
#   4. Add text overlays: title card + "IAS Brief" watermark
#   5. Fade in/out
#   Output: MP4 H.264, AAC audio
# ================================================================

import os
import json
import subprocess


FONT_PATH = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def build_video(clips, voice_path, title, output_path='output.mp4', voice_duration=180):
    """
    Build final MP4 from clips + voice.
    Returns output_path.
    """
    print(f'  📐 Normalizing {len(clips)} clips...')
    normalized = _normalize_clips(clips)

    if not normalized:
        raise Exception('All clip normalizations failed.')

    print('  🔗 Concatenating clips...')
    concat_path = _concatenate_clips(normalized, voice_duration)

    print('  🎨 Rendering final video...')
    _render_final(concat_path, voice_path, title, voice_duration, output_path)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f'  ✅ Final video: {output_path} ({size_mb:.1f} MB)')
    return output_path


# ── Step 1: Normalize ─────────────────────────────────────────────

def _normalize_clips(clips):
    normalized = []
    for i, clip in enumerate(clips):
        out = clip['path'].replace('.mp4', '_norm.mp4')
        cmd = [
            'ffmpeg', '-i', clip['path'],
            '-vf', (
                'scale=1280:720:force_original_aspect_ratio=decrease,'
                'pad=1280:720:(ow-iw)/2:(oh-ih)/2:black,'
                'setsar=1'
            ),
            '-r', '30',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '28',
            '-an',                  # strip original audio
            '-y', out
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0:
            normalized.append(out)
        else:
            print(f'  ⚠️ Normalize failed for clip {i}: {result.stderr.decode()[:120]}')
    return normalized


# ── Step 2: Concatenate (loop to cover voice) ─────────────────────

def _concatenate_clips(normalized, target_sec):
    # Loop clips until we have enough footage
    clips_to_use = []
    total = 0
    while total < target_sec + 10:
        for c in normalized:
            clips_to_use.append(c)
            total += _get_duration(c)
            if total >= target_sec + 10:
                break

    concat_list = 'concat_list.txt'
    with open(concat_list, 'w') as f:
        for c in clips_to_use:
            f.write(f"file '{os.path.abspath(c)}'\n")

    concat_path = 'concat_raw.mp4'
    cmd = [
        'ffmpeg',
        '-f', 'concat', '-safe', '0', '-i', concat_list,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '28',
        '-t', str(int(target_sec) + 3),
        '-an',
        '-y', concat_path
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise Exception('Concat failed: ' + result.stderr.decode()[:300])
    return concat_path


# ── Step 3: Render final with audio + text overlays ───────────────

def _render_final(video_path, audio_path, title, voice_duration, output_path):
    safe_title = _esc(title[:55] + ('…' if len(title) > 55 else ''))

    fade_out_start = max(voice_duration - 1.5, voice_duration * 0.95)

    vf = ','.join([
        # Fade in 1.5s / fade out 1.5s
        f'fade=t=in:st=0:d=1.5',
        f'fade=t=out:st={fade_out_start:.1f}:d=1.5',

        # ── Title card: bottom of screen, visible for first 6 seconds ──
        (
            f"drawtext="
            f"fontfile={FONT_PATH}:"
            f"text='{safe_title}':"
            f"fontsize=38:fontcolor=white:"
            f"x=(w-text_w)/2:y=h*0.83:"
            f"box=1:boxcolor=black@0.65:boxborderw=14:"
            f"enable='between(t,0,6)'"
        ),

        # ── Watermark: top-right, always visible ──
        (
            f"drawtext="
            f"fontfile={FONT_PATH}:"
            f"text='IAS Brief':"
            f"fontsize=22:fontcolor=white@0.75:"
            f"x=w-text_w-18:y=16:"
            f"box=1:boxcolor=black@0.45:boxborderw=8"
        ),
    ])

    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-i', audio_path,
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '24',
        '-c:a', 'aac', '-b:a', '128k',
        '-map', '0:v',
        '-map', '1:a',
        '-shortest',          # trim to whichever ends first (voice)
        '-movflags', '+faststart',
        '-y', output_path
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise Exception('Final render failed: ' + result.stderr.decode()[:400])


# ── Helpers ───────────────────────────────────────────────────────

def _get_duration(path):
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
           '-of', 'json', path]
    result = subprocess.run(cmd, capture_output=True)
    try:
        return float(json.loads(result.stdout)['format']['duration'])
    except Exception:
        return 60


def _esc(text):
    """Escape characters that break FFmpeg drawtext."""
    return (text
            .replace('\\', '\\\\')
            .replace("'",  "\u2019")   # replace straight quote with curly
            .replace(':',  '\\:')
            .replace('%',  '\\%'))
