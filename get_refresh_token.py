#!/usr/bin/env python3
# ================================================================
#  get_refresh_token.py — ONE-TIME SETUP SCRIPT
#
#  Run this ONCE on your local machine (not GitHub Actions).
#  It opens a browser, you log in with your YouTube account,
#  and it prints your refresh token to paste into GitHub Secrets.
#
#  Steps:
#   1. pip install google-auth-oauthlib
#   2. Download client_secrets.json from Google Cloud Console
#      (see SETUP.md Step 3 for instructions)
#   3. python get_refresh_token.py
#   4. Copy the printed values to GitHub Secrets
# ================================================================

import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def main():
    print('🔐 YouTube OAuth Token Generator')
    print('=' * 40)
    print('This will open your browser to log in.')
    print('Make sure client_secrets.json is in this folder.\n')

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            'client_secrets.json',
            scopes=SCOPES
        )
        creds = flow.run_local_server(port=0, prompt='consent')

        print('\n✅ Success! Add these to GitHub Secrets:\n')
        print(f'YOUTUBE_CLIENT_ID     = {creds.client_id}')
        print(f'YOUTUBE_CLIENT_SECRET = {creds.client_secret}')
        print(f'YOUTUBE_REFRESH_TOKEN = {creds.refresh_token}')
        print('\nKeep these private — do NOT commit to GitHub.')

    except FileNotFoundError:
        print('❌ client_secrets.json not found.')
        print('   Download it from Google Cloud Console → APIs & Services → Credentials')
        print('   (see SETUP.md Step 3)')

if __name__ == '__main__':
    main()
