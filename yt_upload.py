# ================================================================
#  yt_upload.py — YouTube Data API v3 Uploader
#  Uses a stored refresh token — no manual login needed in CI.
#  YouTube free quota: 10,000 units/day. Upload costs 1,600 units.
#  → Up to 6 uploads/day free.
# ================================================================

import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request


def upload_video(video_path, title, description, tags,
                 category_id='27',        # 27 = Education
                 privacy='private'):
    """
    Upload an MP4 to YouTube.
    Returns the YouTube video ID string.
    """
    youtube = _get_youtube_service()

    body = {
        'snippet': {
            'title':       title[:100],
            'description': description[:5000],
            'tags':        tags[:15],
            'categoryId':  category_id
        },
        'status': {
            'privacyStatus':            privacy,
            'selfDeclaredMadeForKids':  False
        }
    }

    media = MediaFileUpload(
        video_path,
        mimetype='video/mp4',
        resumable=True,
        chunksize=5 * 1024 * 1024   # 5 MB chunks
    )

    request = youtube.videos().insert(
        part='snippet,status',
        body=body,
        media_body=media
    )

    print(f'  📤 Uploading: {title[:60]}')
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f'  ⬆️  {pct}%', end='\r')

    video_id = response['id']
    print(f'\n  ✅ Live: https://youtube.com/watch?v={video_id}')
    return video_id


# ── Auth ──────────────────────────────────────────────────────────

def _get_youtube_service():
    """Build authenticated YouTube service from environment secrets."""
    creds = Credentials(
        token=None,
        refresh_token=os.environ['YOUTUBE_REFRESH_TOKEN'],
        client_id=os.environ['YOUTUBE_CLIENT_ID'],
        client_secret=os.environ['YOUTUBE_CLIENT_SECRET'],
        token_uri='https://oauth2.googleapis.com/token',
        scopes=['https://www.googleapis.com/auth/youtube.upload']
    )
    creds.refresh(Request())   # exchange refresh token → access token
    return build('youtube', 'v3', credentials=creds)
