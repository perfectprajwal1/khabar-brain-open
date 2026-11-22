"""Tiny Gemini client for khabar-brain. Free tier only. One request per call, never retried.
Any HTTP error (429 quota, 5xx, bad key) raises Stop and the whole run stops. No cards, no paid fallback.
Key comes from env GEMINI_API_KEY (GitHub repo secret). It is never printed or written to disk.
"""
import json, os, re, time, urllib.error, urllib.request

TEXT_MODEL = os.environ.get('GEMINI_TEXT_MODEL', 'gemini-3.5-flash-lite')
TTS_MODEL = 'gemini-2.5-flash-preview-tts'
TTS_VOICE = os.environ.get('GEMINI_TTS_VOICE', 'Sadachbia')
BASE = 'https://generativelanguage.googleapis.com/v1beta/models/'
SPACING_S = 4
_last = [0.0]
COUNT = [0]


class Stop(RuntimeError):
    pass


def _post(model, payload):
    key = os.environ.get('GEMINI_API_KEY', '')
    if not key:
        raise Stop('GEMINI_API_KEY is not set.')
    wait = SPACING_S - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(BASE + model + ':generateContent', data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json', 'x-goog-api-key': key}, method='POST')
    COUNT[0] += 1
    _last[0] = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace')[:300].replace(key, '***')
        if e.code == 429:
            raise Stop('Gemini returned 429 (free-tier limit). Stopped, no retry. ' + body)
        raise Stop(f'Gemini HTTP {e.code}. Stopped, no retry. {body}')
    except Exception as e:
        raise Stop('Gemini request failed (%s). Stopped, no retry.' % type(e).__name__)


def text(prompt, grounded=False, json_out=True, temperature=0.7):
    payload = {'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': {'temperature': temperature}}
    if grounded:
        payload['tools'] = [{'google_search': {}}]
    elif json_out:
        payload['generationConfig']['responseMimeType'] = 'application/json'
    d = _post(TEXT_MODEL, payload)
    try:
        cand = d['candidates'][0]
        out = ''.join(p.get('text', '') for p in cand['content']['parts'])
    except Exception:
        raise Stop('Gemini returned no text: ' + json.dumps(d)[:300])
    meta = cand.get('groundingMetadata', {})
    if not json_out:
        return out, meta
    m = re.search(r'\{.*\}|\[.*\]', out, re.S)
    try:
        return json.loads(m.group(0) if m else out), meta
    except Exception:
        raise Stop('Gemini did not return valid JSON: ' + out[:300])


def speech(prompt):
    """Returns (pcm_bytes, sample_rate)."""
    import base64
    payload = {'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': {
        'responseModalities': ['AUDIO'],
        'speechConfig': {'voiceConfig': {'prebuiltVoiceConfig': {'voiceName': TTS_VOICE}}}}}
    d = _post(TTS_MODEL, payload)
    try:
        part = d['candidates'][0]['content']['parts'][0]['inlineData']
        m = re.search(r'rate=(\d+)', part.get('mimeType', ''))
        return base64.b64decode(part['data']), int(m.group(1)) if m else 24000
    except Exception:
        raise Stop('Gemini TTS returned no audio: ' + json.dumps(d)[:300])


def speech_styled(turns, voice=None, model='gemini-3.8-flash-lite-tts'):
    """Gemini 3.x TTS via the Interactions API: one request, one turn per script line, each with its own
    speech_metadata.style (emotion, pace, volume). Returns (wav_bytes, sample_rate).
    Free tier, one request, no retry. Style strings are short English, the transcript stays verbatim Nepali."""
    import base64
    key = os.environ.get('GEMINI_API_KEY', '')
    if not key:
        raise Stop('GEMINI_API_KEY is not set.')
    content = []
    for t in turns:
        item = {'type': 'text', 'text': t['text']}
        if t.get('style'):
            item['annotations'] = [{'type': 'speech_metadata', 'style': t['style']}]
        content.append(item)
    body = {'model': model, 'input': [{'type': 'user_input', 'content': content}], 'response_format': {'type': 'audio'},
            'generation_config': {'speech_config': [{'voice': voice or TTS_VOICE}]}}
    wait = SPACING_S - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/interactions', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json', 'x-goog-api-key': key}, method='POST')
    COUNT[0] += 1
    _last[0] = time.time()
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        msg = e.read().decode('utf-8', 'replace')[:300].replace(key, '***')
        raise Stop(('Gemini TTS returned 429 (free-tier limit). ' if e.code == 429 else f'Gemini TTS HTTP {e.code}. ') + 'Stopped, no retry. ' + msg)
    except Exception as e:
        raise Stop('Gemini TTS request failed (%s). Stopped, no retry.' % type(e).__name__)

    def find(o):
        if isinstance(o, dict):
            if o.get('type') == 'audio' and 'data' in o:
                return o
            for v in o.values():
                r = find(v)
                if r:
                    return r
        elif isinstance(o, list):
            for v in o:
                r = find(v)
                if r:
                    return r
    a = find(d)
    if not a:
        raise Stop('Gemini TTS returned no audio block.')
    return base64.b64decode(a['data']), 24000


# the earlier working voice approach, kept the same: model gemini-2.5-flash-preview-tts, voice Sadachbia,
# generateContent, one request, a "[DELIVERY ONLY, DO NOT SPEAK: ...]" direction before each paragraph.
# The 12 tone sentences keep their original wording. Our extra emotions (assets/voice/styles.json) are an add-on
# and use the same wrapper sentence with their style text.
KM_TONES = {'curious': 'Say this in a curious, intrigued tone, like a Nepali news presenter asking a question:', 'excited': 'Say this in an excited, energetic tone, like a Nepali news presenter sharing surprising news:', 'serious': 'Say this in a serious, steady tone, like a Nepali news presenter reporting important facts:', 'neutral': 'Say this in a calm, clear, neutral tone, like a Nepali news presenter:', 'warm': 'Say this in a warm, reassuring tone, like a Nepali news presenter giving helpful advice:', 'thinking': 'Say this in a thoughtful, measured tone, like a Nepali news presenter reflecting:', 'confused': 'Say this in a questioning, puzzled tone, like a Nepali news presenter:', 'sad': 'Say this in a subdued, somber tone, like a Nepali news presenter:', 'shocked': 'Say this in a shocked, startled tone, like a Nepali news presenter reporting a surprising event:', 'proud': 'Say this in a proud, uplifting tone, like a Nepali news presenter sharing a achievement:', 'urgent': 'Say this in an urgent, alert tone, like a Nepali news presenter:', 'neutral_talking': 'Say this in a relaxed, conversational, natural tone, like a friendly Nepali news presenter explaining something simply to a viewer:'}


def speech_km(turns):
    """turns: [{'text','emotion','style'}]. Returns (pcm_bytes, rate). Same prompt shape as the earlier project, one request."""
    def tone(t):
        if t['emotion'] in KM_TONES:
            return KM_TONES[t['emotion']]
        return 'Say this in a %s tone, like a Nepali presenter:' % t['style']
    directed = '\n\n'.join('[DELIVERY ONLY, DO NOT SPEAK: ' + tone(t) + ']\n' + t['text'] for t in turns)
    prompt = ('Read the following Nepali paragraphs VERBATIM, in order, in a clear Nepali presenter voice. '
              'Emotion is only in delivery; keep every narration word unchanged. '
              'Bracketed DELIVERY ONLY lines are stage directions, NOT narration: never speak them. '
              'Follow each paragraph delivery direction, without adding words, explanations or repeated words. '
              'Between EACH paragraph, leave one second of complete silence, without speaking the pause instruction. '
              'Read each narration paragraph below exactly once:\n\n' + directed)
    return speech(prompt)
