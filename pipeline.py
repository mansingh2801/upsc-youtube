#!/usr/bin/env python3
import os
import sys
import json
import shutil
import subprocess
from datetime import datetime

USED_FILE = 'used_articles.json'


def load_used_urls():
    try:
        with open(USED_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return []


def save_used_urls(urls):
    with open(USED_FILE, 'w') as f:
        json.dump(urls, f, indent=2)


def commit_used_urls():
    """Commit updated used_articles.json back to the repo."""
    try:
        subprocess.run(['git', 'config', 'user.email', 'actions@github.com'],
                       check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'GitHub Actions'],
                       check=True, capture_output=True)
        subprocess.run(['git', 'add', USED_FILE],
                       check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m',
                        f'[bot] Update used articles — {datetime.now().strftime("%d %b %Y")}'],
                       check=True, capture_output=True)
        subprocess.run(['git', 'push'],
                       check=True, capture_output=True)
        print('  ✅ used_articles.json committed to repo')
    except subprocess.CalledProcessError as e:
        print(f'  ⚠️  Git commit failed: {e}')


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

    source     = article['source']
    voice_path = f'voice_{idx}.wav'
    video_path = f'output_{idx}.mp4'

    print(f'\n{"="*55}')
    print(f'  [{idx}/{total}] {source}: {article["title"][:50]}')
    print(f'{"="*55}')

    try:
        print('\n  📝 Generating script...')
        script_data = generate_upsc_script(article)
        print(f'     Title : {script_data["title"]}')
        print(f'     Points: {len(script_data["key_points"])}')

        print('\n  🎙️  Generating voiceover...')
        _, voice_duration = generate_voice(
            script_data['script'], output_path=voice_path, speed=1.1
        )
        print(f'     Duration: {voice_duration:.1f}s')

        if voice_duration < 30:
            raise Exception(f'Voice too short ({voice_duration:.1f}s)')

        print('\n  ⚙️  Building video...')
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
    print(f'\n✅ {len(articles)} fresh article(s) found')

    used_urls = load_used_urls()
    results   = []

    for i, article in enumerate(articles, 1):
        video_id = process_article(article, i, len(articles))
        results.append((article['source'], video_id))

        # Mark as used immediately after successful upload
        if video_id and article['link'] not in used_urls:
            used_urls.append(article['link'])
            save_used_urls(used_urls)

    # Commit updated used_articles.json to repo
    commit_used_urls()

    print(f'\n{"="*55}\n📊 Summary:')
    for source, vid in results:
        status = f'https://youtube.com/watch?v={vid}' if vid else 'failed'
        print(f'  {"✅" if vid else "❌"} {source}: {status}')

    if all(v is None for _, v in results):
        sys.exit(1)

    print('\n🧹 Done.')


if __name__ == '__main__':
    main()
