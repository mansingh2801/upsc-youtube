import os
import time
from google import genai


def generate_upsc_script(article):
    client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])

    prompt = f"""You are a senior UPSC educator making a 50-second YouTube Short for IAS aspirants.

Source: {article['source']}
Article title: {article['title']}
Article summary: {article['description']}

Generate a complete video package. Reply in EXACTLY this format:

TOPIC: [one-line topic name, under 55 characters]
TITLE: [YouTube title under 70 characters — add #Shorts at end]
DESCRIPTION: [100-word YouTube description ending with #Shorts #UPSC #IAS #CurrentAffairs]
TAGS: [12 comma-separated YouTube tags including Shorts, no #]
KEY_POINTS: [exactly 5 key facts, semicolon-separated, each under 45 characters]

SCRIPT:
[Clean 50-second narration — exactly 110-120 words total.
Start with one punchy hook sentence.
Cover: What happened, why it matters for UPSC.
Mention GS paper relevance.
End with: Follow for daily UPSC updates.]"""

    waits = [20, 40, 60, 90]
    for attempt in range(5):
        try:
            res = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt
            )
            return _parse(res.text.strip(), article)
        except Exception as e:
            if '503' in str(e) and attempt < 4:
                wait = waits[min(attempt, len(waits)-1)]
                print(f'  ⏳ Gemini 503 — retrying in {wait}s (attempt {attempt+1}/5)...')
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
        'key_points':  key_points[:5],
        'script':      script_text,
        'source':      article['source']
    }
