"""Provider layer for the brain. Free tiers only, no cards.
Roles: writer roles (research, script, humanizer) run on WRITER provider; reviewer roles (hook, director) run on
REVIEWER provider, a different model family so the writer does not grade its own work.
Default: writer = Gemini, reviewer = Groq (Qwen). Models are fixed for the whole run, never mixed mid-run.
Rules:
- HTTP 429 from a provider: stop the run. No retry. A whole new run on the other provider needs pk's pre-authorization
  (workflow input writer=groq). The code never switches provider by itself.
- Timeout or 5xx: stop and report. No retry (the outcome of the request is unknown).
- Bad JSON: ONE repair request to the same provider with the broken text and the expected shape. Then stop.
- Every artifact records provider, model and role in draft/llm_log.json.
Keys come from env (GEMINI_API_KEY, GROQ_API_KEY), never printed or stored.
"""
import json, os, re, time, urllib.error, urllib.request

import gemini
from gemini import Stop

GEMINI_MODEL = os.environ.get('GEMINI_TEXT_MODEL', 'gemini-3.8-flash')
GROQ_SPACING_S = int(os.environ.get('GROQ_SPACING_S', '70'))
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'qwen/qwen3.8-27b')   # name verified against Groq's models list 2026-11-23 (qwen3-32b is not offered)
WRITER = os.environ.get('BRAIN_WRITER', 'gemini')
REVIEWER = os.environ.get('BRAIN_REVIEWER', 'groq' if WRITER == 'gemini' else 'gemini')
ROLE_SIDE = {'research': 'writer', 'script': 'writer', 'humanizer': 'writer', 'hook': 'reviewer', 'director': 'reviewer'}
LOG = []
TEXT_FAIL = [False]   # set when a text provider answered 429/5xx or did not answer: the only case the workflow may fail over on
UNKNOWN = [False]     # set when a text request got no answer (timeout, connection): outcome unknown, no automatic replay
FAILOVER_FROM = os.environ.get('BRAIN_FAILOVER_FROM', '')
_last = {}


def provider_for(role):
    return WRITER if ROLE_SIDE[role] == 'writer' else REVIEWER


def _gemini(prompt, temperature):
    gemini.TEXT_MODEL = GEMINI_MODEL
    payload = {'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': {'temperature': temperature, 'responseMimeType': 'application/json'}}
    d = gemini._post(GEMINI_MODEL, payload)
    try:
        return ''.join(p.get('text', '') for p in d['candidates'][0]['content']['parts'])
    except Exception:
        raise Stop('Gemini returned no text: ' + json.dumps(d)[:300])


def _groq(prompt, temperature):
    key = os.environ.get('GROQ_API_KEY', '')
    if not key:
        raise Stop('GROQ_API_KEY is not set.')
    # Groq free tier caps Qwen at ~1000 output tokens per minute. Pace requests so each one gets its own minute.
    # This is pacing, not a retry: a request that fails is never resent.
    wait = GROQ_SPACING_S - (time.time() - _last.get('groq', 0))
    if wait > 0:
        time.sleep(wait)
    body = {'model': GROQ_MODEL, 'messages': [{'role': 'user', 'content': '/no_think\n' + prompt}], 'temperature': temperature, 'max_tokens': 900,
            'response_format': {'type': 'json_object'}}
    req = urllib.request.Request('https://api.groq.com/openai/v1/chat/completions', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key, 'User-Agent': 'khabar-brain'}, method='POST')
    _last['groq'] = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        msg = e.read().decode('utf-8', 'replace')[:300].replace(key, '***')
        if e.code == 429:
            raise Stop('Groq returned 429 (free-tier limit). Stopped, no retry, no automatic switch. ' + msg)
        raise Stop(f'Groq HTTP {e.code}. Stopped, no retry. ' + msg)
    except Exception as e:
        raise Stop('Groq request failed (%s). Stopped, no retry.' % type(e).__name__)
    try:
        t = d['choices'][0]['message']['content']
    except Exception:
        raise Stop('Groq returned no text: ' + json.dumps(d)[:300])
    return re.sub(r'<think>.*?</think>', '', t, flags=re.S)


CALL = {'gemini': (_gemini, lambda: GEMINI_MODEL), 'groq': (_groq, lambda: GROQ_MODEL)}


def _parse(t):
    m = re.search(r'\{.*\}|\[.*\]', t, re.S)
    return json.loads(m.group(0) if m else t)


def run(role, prompt, temperature=0.6, shape=''):
    prov = provider_for(role)
    if prov not in CALL:
        raise Stop('Unknown provider ' + prov)
    fn, model = CALL[prov]
    try:
        raw = fn(prompt, temperature)
    except Stop as e:
        if re.search(r'429|HTTP 5\d\d', str(e)):
            TEXT_FAIL[0] = True          # the provider ANSWERED with a refusal: outcome known, failover allowed
        elif re.search(r'request failed', str(e)):
            UNKNOWN[0] = True            # timeout / no answer: outcome unknown, never replayed automatically
        raise
    repaired = False
    try:
        obj = _parse(raw)
    except Exception:
        repaired = True      # exactly one repair request, same provider
        raw2 = fn('The text below was supposed to be ONE valid JSON object' + (' shaped like: ' + shape if shape else '') +
                  '. Return ONLY the corrected JSON, change no content.\n\n' + raw[:12000], 0.0)
        try:
            obj = _parse(raw2)
        except Exception:
            raise Stop(f'{prov} returned invalid JSON twice for role {role}. Stopped.')
    LOG.append({'role': role, 'provider': prov, 'model': model(), 'json_repaired': repaired, 'at': time.strftime('%H:%M:%S')})
    return obj, {'provider': prov, 'model': model(), 'role': role}


def save_log(path):
    import pathlib
    pathlib.Path(path).write_text(json.dumps({'writer': WRITER, 'reviewer': REVIEWER, 'failover_from': FAILOVER_FROM or None,
                                              'reviewer_independent': WRITER != REVIEWER, 'calls': LOG,
                                              'note': 'Models are fixed per run, never mixed mid-run. Reviewer is a different provider unless reviewer=same was set.'}, indent=2))


def preflight(need_tts=True):
    """Fail BEFORE any request if a key for a planned provider is missing, so no quota is spent on a doomed run."""
    need = {WRITER, REVIEWER} | ({'gemini'} if need_tts else set())
    for prov in need:
        env = {'gemini': 'GEMINI_API_KEY', 'groq': 'GROQ_API_KEY'}.get(prov)
        if not env or not os.environ.get(env):
            raise Stop(f'{prov}: key {env} is not set. Nothing was requested.')
