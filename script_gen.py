# ================================================================
#  script_gen.py — UPSC Script Generator (DeepSeek API)
#  DeepSeek API is OpenAI-compatible → same library, different URL
# ================================================================

import os
from openai import OpenAI


def generate_upsc_script(topic=None):
    """
    Generate a complete 3-minute UPSC educational video script.
    Returns a dict with: topic, title, description, tags, keywords, script
    """
    client = OpenAI(
        api_key=os.environ['DEEPSEEK_API_KEY'],
        base_url='https://api.deepseek.com'
    )

    # Step 1 — pick a topic if none given
    if not topic:
        topic_res = client.chat.completions.create(
            model='deepseek-chat',
            messages=[{
                'role': 'user',
                'content': (
                    'You are a UPSC expert. Suggest ONE important current affairs topic '
                    'for UPSC 2025-26 preparation (Prelims + Mains relevant). '
                    'Reply with ONLY the topic name. Nothing else.'
                )
            }],
            max_tokens=60
        )
        topic = topic_res.choices[0].message.content.strip()

    # Step 2 — generate full script package
    prompt = f"""You are a senior UPSC educator making a faceless YouTube video for IAS aspirants.

Topic: {topic}

Generate a complete video package. Reply in EXACTLY this format (keep all labels):

TOPIC: {topic}
TITLE: [YouTube title — compelling, under 70 characters, no clickbait]
DESCRIPTION: [150-word YouTube description. Include: what this video covers, UPSC relevance, call to action. End with 8 hashtags: #UPSC #IAS #CurrentAffairs etc.]
TAGS: [12 comma-separated YouTube tags, no #]
KEYWORDS: [6 comma-separated keywords for stock footage search, e.g. "India parliament, policy document, government meeting, Indian map, economy growth, infrastructure"]

SCRIPT:
[Write a clean 3-minute narration script — approximately 420-450 words.
Rules:
- Open with a surprising fact or question (hook)
- Cover: What happened | Background context | Why it matters for India | UPSC exam angle
- End with: "Like and subscribe for daily UPSC current affairs."
- Plain English, no emojis, no stage directions, no timestamps
- Factual and precise — numbers, dates, names where relevant]"""

    res = client.chat.completions.create(
        model='deepseek-chat',
        messages=[{'role': 'user', 'content': prompt}],
        max_tokens=1800
    )

    raw = res.choices[0].message.content.strip()
    return _parse_script_response(raw, topic)


def _parse_script_response(raw, topic):
    """Parse the structured response into a clean dict."""

    def extract_line(label):
        for line in raw.split('\n'):
            stripped = line.strip()
            if stripped.upper().startswith(label.upper() + ':'):
                return stripped[len(label) + 1:].strip()
        return ''

    script_start = raw.find('SCRIPT:')
    script_text = raw[script_start + 7:].strip() if script_start != -1 else raw

    tags_raw = extract_line('TAGS')
    tags = [t.strip().lstrip('#') for t in tags_raw.split(',') if t.strip()]

    return {
        'topic':       extract_line('TOPIC') or topic,
        'title':       extract_line('TITLE'),
        'description': extract_line('DESCRIPTION'),
        'tags':        tags[:12],
        'keywords':    extract_line('KEYWORDS'),
        'script':      script_text
    }
