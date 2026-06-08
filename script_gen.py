import os
from google import genai


def generate_upsc_script(topic=None):
    client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])

    if not topic:
        topic_res = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=(
                'You are a UPSC expert. Suggest ONE important current affairs topic '
                'for UPSC 2026-27 preparation (Prelims + Mains relevant). '
                'Reply with ONLY the topic name. Nothing else.'
            )
        )
        topic = topic_res.text.strip()

    prompt = f"""You are a senior UPSC educator making a faceless YouTube video for IAS aspirants.

Topic: {topic}

Generate a complete video package. Reply in EXACTLY this format:

TOPIC: {topic}
TITLE: [YouTube title under 70 characters]
DESCRIPTION: [150-word YouTube description ending with 8 hashtags]
TAGS: [12 comma-separated YouTube tags]
KEYWORDS: [6 comma-separated stock footage search keywords]

SCRIPT:
[Clean 3-minute narration, 420-450 words, no emojis, no stage directions.
Open with a hook. Cover: What, Background, Why it matters, UPSC angle.
End with: Like and subscribe for daily UPSC current affairs.]"""

    res = client.models.generate_content(
        model='gemini-3.5-flash',
        contents=prompt
    )
    return _parse_script_response(res.text.strip(), topic)


def _parse_script_response(raw, topic):
    def extract_line(label):
        for line in raw.split('\n'):
            if line.strip().upper().startswith(label.upper() + ':'):
                return line.strip()[len(label)+1:].strip()
        return ''

    script_start = raw.find('SCRIPT:')
    script_text = raw[script_start + 7:].strip() if script_start != -1 else raw
    tags = [t.strip().lstrip('#') for t in extract_line('TAGS').split(',') if t.strip()]

    return {
        'topic':       extract_line('TOPIC') or topic,
        'title':       extract_line('TITLE'),
        'description': extract_line('DESCRIPTION'),
        'tags':        tags[:12],
        'keywords':    extract_line('KEYWORDS'),
        'script':      script_text
    }
