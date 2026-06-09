# ================================================================
#  script_gen.py — UPSC Script Generator (Gemini 3.5 Flash)
#  Accepts a fetched article as context for the video script
# ================================================================

import os
from google import genai


def generate_upsc_script(article):
    """
    Generate a 3-minute UPSC video script based on a real article.
    article: dict with keys — source, title, description, link
    Returns dict: topic, title, description, tags, keywords, script
    """
    client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])

    prompt = f"""You are a senior UPSC educator making a faceless YouTube video for IAS aspirants.

Source: {article['source']}
Article title: {article['title']}
Article summary: {article['description']}

Generate a complete video package. Reply in EXACTLY this format:

TOPIC: [one-line topic name]
TITLE: [YouTube title under 70 characters — compelling, UPSC-relevant]
DESCRIPTION: [150-word YouTube description ending with 8 hashtags like #UPSC #IAS #CurrentAffairs]
TAGS: [12 comma-separated YouTube tags, no #]
KEYWORDS: [6 comma-separated stock footage search keywords relevant to the topic]

SCRIPT:
[Clean 3-minute narration, 420-450 words, no emojis, no stage directions.
Open with a surprising fact or hook question about this article.
Cover: What happened | Background context | Why it matters for India | UPSC exam angle (GS paper, related topics, possible questions).
End with: Like and subscribe for daily UPSC current affairs.]"""

import time
    for attempt in range(3):
        try:
            res = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt
            )
            return _parse(res.text.strip(), article['title'])
        except Exception as e:
            if '503' in str(e) and attempt < 2:
                wait = (attempt + 1) * 20
                print(f'  ⏳ Gemini 503 — retrying in {wait}s...')
                time.sleep(wait)
            else:
                raise

def _parse(raw, fallback_topic):
    def extract(label):
        for line in raw.split('\n'):
            if line.strip().upper().startswith(label.upper() + ':'):
                return line.strip()[len(label)+1:].strip()
        return ''

    script_start = raw.find('SCRIPT:')
    script_text  = raw[script_start + 7:].strip() if script_start != -1 else raw
    tags = [t.strip().lstrip('#') for t in extract('TAGS').split(',') if t.strip()]

    return {
        'topic':       extract('TOPIC') or fallback_topic,
        'title':       extract('TITLE'),
        'description': extract('DESCRIPTION'),
        'tags':        tags[:12],
        'keywords':    extract('KEYWORDS'),
        'script':      script_text
    }
