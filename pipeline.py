#!/usr/bin/env python3
# ================================================================
#  pipeline.py — IAS Brief YouTube Auto-Publisher
#  Fetches yesterday's articles from PIB, SEBI, RBI
#  Generates and uploads one video per source daily
# ================================================================

import os
import sys
import shutil
from datetime import datetime


def cleanup(paths=None):
    targets = paths or ['clips', 'voice.wav', 'concat_raw.mp4',
                        'concat_list.txt', 'output.mp4']
    for p in targets:
        try:
            if os.path.isfile(p):   os.remove(p)
            elif os.path.isdir(p):  shutil.rmtree(p)
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
    """Run the full pipeline for one article. Returns video_id or None."""
    from script_gen  import generate_upsc_script
    from voice_gen   import generate_voice
    from footage     import download_clips
    from video_build import build_video
    from yt_upload   import upload_video

    source = article['source']
    print(f'\n{"="*55}')
    print(f'  [{idx}/{total}] {source}: {article["title"][:50]}')
    print(f'{"="*55}')

    # Unique filenames per article to avoid conflicts
    voice_path  = f'voice_{idx}.wav'
    video_path  = f'output_{idx}.mp4'

    try:
        print(f'\n  📝 Generating script...')
        script_data = generate_upsc_script(article)
        print(f'     Title   : {script_data["title"]}')
        print(f'     Words   : {len(script_data["script"].split())}')

        print(f'\n  🎙️  Generating voiceover...')
        _, voice_duration = generate_voice(script_data['script'],
                                           output_path=voice_path)
        print(f'     Duration: {voice_duration:.1f}s')

        if voice_duration < 30:
            raise Exception(f'Voice too short ({voice_duration:.1f}s)')

        print(f'\n  🎬 Fetching footage...')
        clips = download_clips(script_data['keywords'], voice_duration)

        print(f'\n  ⚙️  Building video...')
        build_video(clips=clips, voice_path=voice_path,
                    title=script_data['title'],
                    output_path=video_path,
                    voice_duration=voice_duration)

        print(f'\n  📤 Uploading to YouTube...')
        video_id = upload_video(
            video_path  = video_path,
            title       = f'[{source}] {script_data["title"]}',
            description = script_data['description'],
            tags        = script_data['tags']
        )

        cleanup([voice_path, video_path, 'clips',
                 'concat_raw.mp4', 'concat_list.txt'])
        return video_id

    except Exception as e:
        print(f'\n  ❌ Failed [{source}]: {e}')
        cleanup([voice_path, video_path, 'clips',
                 'concat_raw.mp4', 'concat_list.txt'])
        return None


def main():
    print(f'\n🎬 IAS Brief Pipeline — {datetime.now().strftime("%d %b %Y %H:%M UTC")}')
    print('Sources: PIB | SEBI | RBI')
    print('=' * 55)

    check_env()

    from fetch_articles import fetch_articles

    articles = fetch_articles()
    print(f'\n✅ {len(articles)} article(s) found\n')

    results = []
    for i, article in enumerate(articles, 1):
        video_id = process_article(article, i, len(articles))
        results.append((article['source'], video_id))

    print(f'\n{"="*55}')
    print('📊 Summary:')
    for source, vid in results:
        if vid:
            print(f'  ✅ {source}: https://youtube.com/watch?v={vid}')
        else:
            print(f'  ❌ {source}: failed')

    failed = [s for s, v in results if not v]
    if len(failed) == len(results):
        print('\n❌ All articles failed.')
        sys.exit(1)

    print('\n🧹 Done.')


if __name__ == '__main__':
    main()
