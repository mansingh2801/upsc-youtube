# UPSC YouTube Auto-Publisher — Setup Guide

One-time setup. After this, a new YouTube video uploads itself every day at 7 AM IST.

---

## What you need (all free)

| Service | What for | Free limit |
|---|---|---|
| GitHub | Hosts code + runs automation | 2,000 min/month (or unlimited if repo is public) |
| DeepSeek API | Generates UPSC script | Free tier, generous quota |
| Pexels API | Stock video footage | 200 req/hour |
| YouTube Data API | Auto-uploads video | 10,000 units/day (~6 uploads/day) |
| Google Cloud | YouTube API access | Free |

---

## Step 1 — Create GitHub repo

1. Go to https://github.com/new
2. Name it `upsc-youtube` (or anything you like)
3. Set it to **Public** (unlimited free Actions minutes)
4. Click **Create repository**
5. Upload all files from this zip into the repo root

---

## Step 2 — Get DeepSeek API Key

1. Go to https://platform.deepseek.com
2. Sign up (free)
3. Go to **API Keys** → **Create API Key**
4. Copy the key (starts with `sk-`)

---

## Step 3 — Get Pexels API Key

1. Go to https://www.pexels.com/api
2. Sign up (free) → **Your API Key**
3. Copy the key

---

## Step 4 — Get YouTube API credentials (hardest step)

### 4a. Create Google Cloud project
1. Go to https://console.cloud.google.com
2. Click **Select a project** → **New Project** → name it `upsc-youtube`
3. Click **Create**

### 4b. Enable YouTube Data API
1. In Google Cloud Console → **APIs & Services** → **Library**
2. Search **YouTube Data API v3** → Click it → **Enable**

### 4c. Create OAuth credentials
1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. If prompted, configure consent screen first:
   - User type: **External**
   - App name: `UPSC YouTube Bot`
   - Add your email as test user
   - Save
4. Back to Create Credentials → OAuth client ID:
   - Application type: **Desktop app**
   - Name: `upsc-youtube`
   - Click **Create**
5. Click **Download JSON** → save as `client_secrets.json`

### 4d. Get your refresh token (one-time, on your PC)
1. Install Python on your PC if not already: https://python.org
2. Open Command Prompt (Windows) or Terminal (Mac/Linux)
3. Run: `pip install google-auth-oauthlib`
4. Put `client_secrets.json` and `get_refresh_token.py` in the same folder
5. Run: `python get_refresh_token.py`
6. Browser opens → log in with your YouTube channel's Google account
7. Allow the permissions
8. Terminal prints 3 values — copy all three

---

## Step 5 — Add secrets to GitHub

1. Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** for each:

| Secret name | Value |
|---|---|
| `DEEPSEEK_API_KEY` | From Step 2 |
| `PEXELS_API_KEY` | From Step 3 |
| `YOUTUBE_CLIENT_ID` | From Step 4d |
| `YOUTUBE_CLIENT_SECRET` | From Step 4d |
| `YOUTUBE_REFRESH_TOKEN` | From Step 4d |

Optional (for Pixabay fallback footage):

| Secret name | Value |
|---|---|
| `PIXABAY_API_KEY` | From https://pixabay.com/api/docs (free signup) |

---

## Step 6 — Test run

1. Go to your GitHub repo → **Actions** tab
2. Click **📺 UPSC Daily YouTube Upload** in the left panel
3. Click **Run workflow** → **Run workflow** (green button)
4. Watch the logs — should take 10-20 minutes
5. Check your YouTube channel — video should appear!

---

## After setup

- Video uploads automatically every day at 7 AM IST
- You can also trigger manually anytime from **Actions → Run workflow**
- To change the topic: edit `script_gen.py` → `generate_upsc_script(topic='your topic')`

---

## Troubleshooting

| Error | Fix |
|---|---|
| `Missing GitHub Secrets` | Re-check Step 5, all 5 secrets must be added |
| `Kokoro model download failed` | Re-run — first run downloads the model (~300 MB) |
| `No footage downloaded` | Check PEXELS_API_KEY is correct |
| `YouTube upload quota exceeded` | Wait until midnight Pacific time (quota resets) |
| `OAuth token expired` | Re-run `get_refresh_token.py` and update YOUTUBE_REFRESH_TOKEN |

---

## File reference

```
upsc-youtube/
├── .github/workflows/daily.yml   ← GitHub Actions schedule
├── pipeline.py                   ← Main orchestrator
├── script_gen.py                 ← DeepSeek script generation
├── voice_gen.py                  ← Kokoro TTS voiceover
├── footage.py                    ← Pexels/Pixabay download
├── video_build.py                ← FFmpeg video assembly
├── yt_upload.py                  ← YouTube upload
├── get_refresh_token.py          ← Run once to get YouTube token
├── requirements.txt              ← Python packages
└── SETUP.md                      ← This file
```
