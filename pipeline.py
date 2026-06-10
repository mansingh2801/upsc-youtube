#!/usr/bin/env python3
# ================================================================
#  pipeline.py — IAS Brief YouTube Auto-Publisher
#  Dark background + text overlay style (no stock footage)
#  3 videos/day: PIB | SEBI | RBI
# ================================================================

import os
import sys
import shutil
from datetime import datetime


def cleanup(paths=None):
    for p in (paths or ['voice.wav', 'concat_raw.mp4',
                         'concat_list.txt', 'output.mp4', 'clips']):
        try:
            if os.path.isfile(p):  os.remove(p)
            elif os.path.isdir(p): shutil.rmtree(p)
        except Exception:
            pass


def check_env():
    required = ['GEMINI_API_KEY', 'PEXELS_API_KEY',
                 'YOUTUBE_CLIENT_ID', 'YOUTUBE_CLIENT_SECRET',
                 'YOUTUBE_REFRESH_TOKEN']
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f'❌ Missing GitHub Secrets: {", ".join(missing)}')
        sys.exit(1)


def process_article(article, idx, total):
    from script_gen  import generate_upsc_script
    from voice_gen   import generate_voice
    from video_build import build_video
    from yt_upload   import upload_video

    source      = article['source']
    voice_path  = f'voice_{idx}.wav'
    video_path  = f'output_{idx}.mp4'

    print(f'\n{"="*55}')
    print(f'  [{idx}/{total}] {source}: {article["title"][:50]}')
    print(f'{"="*55}')

    try:
        print('\n  📝 Generating script...')
        script_data = generate_upsc_script(article)
        print(f'     Title      : {script_data["title"]}')
        print(f'     Key points : {len(script_data["key_points"])}')

        print('\n  🎙️  Generating voiceover...')
        _, voice_duration = generate_voice(
            script_data['script'], output_path=voice_path
        )
        print(f'     Duration: {voice_duration:.1f}s')

        if voice_duration < 30:
            raise Exception(f'Voice too short ({voice_duration:.1f}s)')

        print('\n  ⚙️  Building video (dark background + text)...')
        build_video(
            script_data    = script_data,
            voice_path     = voice_path,
            output_path    = video_path,
            voice_duration = voice_duration
        )

        print('\n  📤 Uploading to YouTube...')
        video_id = upload_video(
            video_path  = video_path,
            title       = f'[{source}] {script_data["title"]}',
            description = script_data['description'],
            tags        = script_data['tags']
        )

        cleanup([voice_path, video_path])
        return video_id

    except Exception as e:
        print(f'\n  ❌ Failed [{source}]: {e}')
        cleanup([voice_path, video_path])
        return None


def main():
    print(f'\n🎬 IAS Brief Pipeline — {datetime.now().strftime("%d %b %Y %H:%M UTC")}')
    print('Sources: PIB | SEBI | RBI')
    print('=' * 55)

    check_env()

    from fetch_articles import fetch_articles
    articles = fetch_articles()
    print(f'\n✅ {len(articles)} article(s) found')

    results = []
    for i, article in enumerate(articles, 1):
        video_id = process_article(article, i, len(articles))
        results.append((article['source'], video_id))

    print(f'\n{"="*55}\n📊 Summary:')
    for source, vid in results:
        status = f'https://youtube.com/watch?v={vid}' if vid else 'failed'
        print(f'  {"✅" if vid else "❌"} {source}: {status}')

    if all(v is None for _, v in results):
        sys.exit(1)

    print('\n🧹 Done.')


if __name__ == '__main__':
    main()
