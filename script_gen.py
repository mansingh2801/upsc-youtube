import os
import time
from google import genai


def generate_upsc_script(article):
    client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])

    prompt = f"""You are a senior UPSC educator making a faceless YouTube video for IAS aspirants.

Source: {article['source']}
Article title: {article['title']}
Article summary: {article['description']}

Generate a complete video package. Reply in EXACTLY this format:

TOPIC: [one-line topic name, under 55 characters]
TITLE: [YouTube title under 70 characters]
DESCRIPTION: [150-word YouTube description ending with 8 hashtags like #UPSC #IAS #CurrentAffairs]
TAGS: [12 comma-separated YouTube tags, no #]
KEYWORDS: [6 comma-separated stock footage search keywords]
KEY_POINTS: [exactly 5 key facts, semicolon-separated, each under 52 characters, UPSC exam relevant]

SCRIPT:
[Clean 3-minute narration, 420-450 words, no emojis, no stage directions.
Open with a hook. Cover: What happened, Background, Why it matters, UPSC angle.
Include GS paper relevance and possible exam question angle.
End with: Like and subscribe for daily UPSC current affairs.]"""

    for attempt in range(3):
        try:
            res = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt
            )
            return _parse(res.text.strip(), article)
        except Exception as e:
            if '503' in str(e) and attempt < 2:
                wait = (attempt + 1) * 20
                print(f'  ⏳ Gemini 503 — retrying in {wait}s...')
                time.sleep(wait)
            else:
                raise


def _parse(raw, article):
    def extract(label):
        for line in raw.split('\n'):
            if line.strip().upper().startswith(label.upper() + ':'):
                return line.strip()[len(label)+1:].strip()
        return ''

    script_start = raw.find('SCRIPT:')
    script_text  = raw[script_start + 7:].strip() if script_start != -1 else raw
    tags         = [t.strip().lstrip('#') for t in extract('TAGS').split(',') if t.strip()]
    key_points   = [p.strip() for p in extract('KEY_POINTS').split(';') if p.strip()]

    return {
        'topic':       extract('TOPIC') or article['title'],
        'title':       extract('TITLE'),
        'description': extract('DESCRIPTION'),
        'tags':        tags[:12],
        'keywords':    extract('KEYWORDS'),
        'key_points':  key_points[:5],
        'script':      script_text,
        'source':      article['source']
    }
