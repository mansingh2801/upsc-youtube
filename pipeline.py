#!/usr/bin/env python3
# ================================================================
#  pipeline.py — UPSC YouTube Auto-Publisher
#  Run by GitHub Actions daily at 7 AM IST
#
#  Flow:
#   GEMINI → Script
#   Kokoro   → Voice (WAV)
#   Pexels   → Stock footage clips
#   FFmpeg   → Final MP4
#   YouTube  → Auto-upload
# ================================================================

import os
import sys
import shutil
from datetime import datetime


def cleanup():
    """Remove all temporary files created during the run."""
    for path in ['clips', 'voice.wav', 'concat_raw.mp4',
                 'concat_list.txt', 'output.mp4']:
        try:
            if os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
        except Exception:
            pass

def check_env():
    """Verify all required environment variables are set."""
    required = [
        'GEMINI_API_KEY',
        'PEXELS_API_KEY',
        'YOUTUBE_CLIENT_ID',
        'YOUTUBE_CLIENT_SECRET',
        'YOUTUBE_REFRESH_TOKEN'
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f'❌ Missing GitHub Secrets: {", ".join(missing)}')
        sys.exit(1)


def main():
    print(f'\n🎬 UPSC YouTube Pipeline — {datetime.now().strftime("%d %b %Y %H:%M UTC")}')
    print('=' * 55)

    check_env()

    # Import here so missing packages give a clear error message
    from script_gen  import generate_upsc_script
    from voice_gen   import generate_voice
    from footage     import download_clips
    from video_build import build_video
    from yt_upload   import upload_video

    try:
        # ── Step 1: Generate Script ───────────────────────────────
        print('\n📝 Step 1 / 5 — Generating script (DeepSeek)...')
        script_data = generate_upsc_script()
        print(f'  Topic   : {script_data["topic"]}')
        print(f'  Title   : {script_data["title"]}')
        print(f'  Words   : {len(script_data["script"].split())}')

        # ── Step 2: Generate Voiceover ────────────────────────────
        print('\n🎙️  Step 2 / 5 — Generating voiceover (Kokoro TTS)...')
        voice_path, voice_duration = generate_voice(script_data['script'])
        print(f'  Duration: {voice_duration:.1f}s')

        if voice_duration < 30:
            raise Exception(f'Voice too short ({voice_duration:.1f}s) — script may be empty.')

        # ── Step 3: Download Stock Footage ────────────────────────
        print('\n🎬 Step 3 / 5 — Fetching stock footage (Pexels/Pixabay)...')
        clips = download_clips(script_data['keywords'], voice_duration)

        # ── Step 4: Build Video ───────────────────────────────────
        print('\n⚙️  Step 4 / 5 — Building video (FFmpeg)...')
        video_path = build_video(
            clips          = clips,
            voice_path     = voice_path,
            title          = script_data['title'],
            output_path    = 'output.mp4',
            voice_duration = voice_duration
        )

        # ── Step 5: Upload to YouTube ─────────────────────────────
        print('\n📤 Step 5 / 5 — Uploading to YouTube...')
        video_id = upload_video(
            video_path  = video_path,
            title       = script_data['title'],
            description = script_data['description'],
            tags        = script_data['tags']
        )

        print(f'\n✅ Pipeline complete!')
        print(f'   Watch: https://youtube.com/watch?v={video_id}')

    except Exception as err:
        print(f'\n❌ Pipeline failed: {err}')
        cleanup()
        sys.exit(1)

    cleanup()
    print('🧹 Temp files removed. Done.')


if __name__ == '__main__':
    main()
