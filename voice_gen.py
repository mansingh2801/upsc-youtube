# ================================================================
#  voice_gen.py — Kokoro TTS Voiceover Generator
#  Kokoro-82M: free, open-source, high-quality English TTS
#  Model auto-downloads from HuggingFace on first run (~300 MB)
#  Cached in GitHub Actions → fast on subsequent runs
# ================================================================

import numpy as np
import soundfile as sf


def generate_voice(script_text, output_path='voice.wav', speed=0.95):
    """
    Convert script text to WAV audio using Kokoro TTS.
    Returns (output_path, duration_in_seconds).
    speed: 0.9 = slower/clearer, 1.0 = normal, 1.1 = faster
    """
    from kokoro import KPipeline

    print('  🤖 Loading Kokoro model...')
    pipeline = KPipeline(lang_code='a')   # 'a' = American English

    # Split into sentences for better prosody
    sentences = _split_into_sentences(script_text)
    print(f'  📜 Processing {len(sentences)} sentences...')

    all_audio = []
    sample_rate = 24000

    for i, sentence in enumerate(sentences):
        if not sentence.strip():
            continue

        try:
            generator = pipeline(
                sentence,
                voice='af_heart',     # warm, clear female voice
                speed=speed,
                split_pattern=None
            )
            for _, _, audio in generator:
                all_audio.append(audio)
                # natural pause between sentences (0.18s)
                all_audio.append(np.zeros(int(sample_rate * 0.18)))

        except Exception as e:
            print(f'  ⚠️ Sentence {i+1} skipped: {e}')

    if not all_audio:
        raise Exception('Kokoro generated no audio. Check script text.')

    combined = np.concatenate(all_audio).astype(np.float32)
    sf.write(output_path, combined, sample_rate)

    duration = len(combined) / sample_rate
    print(f'  ✅ Voice saved: {output_path} ({duration:.1f}s)')
    return output_path, duration


def _split_into_sentences(text):
    """Split script into clean sentences for TTS processing."""
    import re
    # Flatten newlines, split on sentence boundaries
    text = text.replace('\n', ' ').strip()
    sentences = re.split(r'(?<=[.!?])\s+', text)
    # Filter empty, strip whitespace
    return [s.strip() for s in sentences if s.strip()]
