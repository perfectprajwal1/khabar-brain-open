#!/usr/bin/env python3
"""khabar-brain: topic + 2-source research -> Nepali script -> humanizer -> hook score -> icon/demo/voice plan
-> validator -> Gemini voice. Free tier only. Any Gemini limit or error stops the whole run. No posting.

Usage: brain.py OUTDIR [--topic "text"] [--voice NAME] [--no-voice]
Writes OUTDIR/: research.json script.json hook.json plan.json validation.json (+ voice.wav voice.mp3 words.json icons.json demo.json)
Text requests per run: research, script, humanizer (writer provider), hook, director (reviewer provider) = 5, plus 1 Gemini TTS request.
Exit: 0 passed, 2 validator/hook rejected the draft (nothing sent to the GPU), 1 error or Gemini limit.
"""
import json, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gemini, llm
from gemini import Stop

HERE = Path(__file__).resolve().parent.parent


def _die(t, v, tb):
    # exit codes: 4 = text provider answered 429/5xx, the only case the workflow fails over on. 6 = a request got NO answer (timeout), outcome unknown: no failover, a human decides. 5 = other Gemini stop (TTS etc). 1 = anything else.
    import traceback, os
    traceback.print_exception(t, v, tb)
    try:
        llm.save_log(out / 'llm_log.json')
    except Exception:
        pass
    os._exit(6 if (issubclass(t, Stop) and llm.UNKNOWN[0] and not llm.TEXT_FAIL[0]) else 4 if (issubclass(t, Stop) and llm.TEXT_FAIL[0]) else 5 if issubclass(t, Stop) else 1)


sys.excepthook = _die
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
arg = lambda n, d=None: sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d
topic_in, voice_name, no_voice = arg('--topic'), arg('--voice', gemini.TTS_VOICE), '--no-voice' in sys.argv
STYLES = json.loads((HERE / 'assets/voice/styles.json').read_text())
STYLES.pop('_note', None)
PRON = json.loads((HERE / 'assets/voice/pronunciations.json').read_text())
PRON.pop('_note', None)
ICONS = json.loads((HERE / 'assets/icons.json').read_text())
sk = lambda n: (HERE / 'skills' / n / 'SKILL.md').read_text()


def save(name, obj):
    (out / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def summary(t):
    import os
    f = os.environ.get('GITHUB_STEP_SUMMARY')
    print(t, flush=True)
    if f:
        open(f, 'a').write(t + '\n')


llm.preflight(need_tts=not no_voice)
# 1. topic from the source pack + claims quoted from fetched pages (one request, no search grounding)
import datetime, sourcepack
PACK = json.loads((HERE / 'assets/source_pack.json').read_text())['topics']
if topic_in:
    pick = [t for t in PACK if topic_in.lower() in (t['id'] + ' ' + t['topic']).lower()]
    if not pick:
        raise Stop('Topic %r is not in assets/source_pack.json. Ids: %s' % (topic_in, ', '.join(t['id'] for t in PACK)))
    entry = pick[0]
else:
    entry = PACK[datetime.date.today().toordinal() % len(PACK)]
pages = sourcepack.fetch_topic(entry)
save('pack.json', {'topic': entry['topic'], 'pages': pages})
p = f"""You are the research ledger for short Nepali explainer reels on useful digital skills for Nepali students and early-career workers.
{sk('source-ledger')}
Topic: {entry['topic']}
You may ONLY use facts that appear in the page texts below. Do not use outside knowledge, do not invent URLs, dates or numbers.
Write exactly 3 small, concrete claims for the reel. Each claim needs a supporting quote from EACH of the 2 pages (different publishers). A quote must be copied VERBATIM from that page's text (20 to 220 characters, no edits, no ellipsis).
Pages:
{json.dumps([{'publisher': x['publisher'], 'url': x['url'], 'text': x['text']} for x in pages], ensure_ascii=False)}
Reply ONLY JSON: {{"topic":"{entry['topic']}","why_useful":"...","claims":[{{"id":"c1","text":"claim in English","sources":[{{"publisher":"...","url":"exact page url given above","quote":"verbatim quote"}}]}}],"local_fit_inference":"separate inference for Nepali students, not a fact"}}"""
research, m = llm.run('research', p, temperature=0.3, shape='{"topic":"","claims":[{"id":"c1","text":"","sources":[{"publisher":"","url":"","quote":""}]}]}')
research['_llm'] = m
research['demo_query'] = entry['demo_query']
research['signal'] = {'platform': 'source pack (curated official pages)', 'region': 'global', 'metric': 'none, topic chosen from a curated list, not a trend', 'scope': 'none'}
save('research.json', research)
print('research ok:', research.get('topic'), flush=True)

# 2. spoken Nepali script
p = f"""{sk('nepali-editor')}
{sk('script-writer')}
{sk('topic-picker')}
Research ledger (facts you may use, nothing else):
{json.dumps({'topic': research['topic'], 'claims': [{'id': c['id'], 'text': c['text']} for c in research['claims']]}, ensure_ascii=False)}
Write a 20 to 25 second reel script: 5 or 6 short lines, about 45 to 55 Nepali words in total, written in Devanagari ONLY (write English terms like ChatGPT or Gmail in Devanagari, e.g. च्याटजीपीटी). Line 1 is the hook. The last line is a short useful takeaway, no 'follow/like/subscribe' begging.
Every factual line must list the claim ids it uses; non-factual lines (hook question, takeaway) use [].
{sk('voice-director')}
For each line YOU choose the emotion that fits its meaning, from this list of names with their delivery: {json.dumps(STYLES, ensure_ascii=False)}. Design an arc and vary the emotions, never flat.
Reply ONLY JSON: {{"lines":[{{"n":1,"text":"...","claims":["c1"],"emotion":"curious","role":"hook|body|takeaway"}}],"pronunciations":{{"Latin term":"देवनागरी"}},"flags":["lines whose meaning was hard to keep"]}}"""
script, m = llm.run('script', p, shape='{"lines":[{"n":1,"text":"","claims":[],"emotion":"","role":""}],"pronunciations":{}}')
script['_llm'] = m
save('script.json', script)

# 3. humanizer
p = f"""{sk('humanizer')}
You are a humanizer for spoken Nepali. Rewrite the lines below so they sound like a friendly young Nepali creator talking to a friend, not like a translation or a news bulletin.
Keep: the same number of lines, every claim id list, every fact and number exactly, the emotion field, Devanagari only. Do not add facts or slang you are not sure about. Short breath-length sentences. Use natural fillers sparingly (हेर्नुस्, ल, ए).
Input: {json.dumps(script['lines'], ensure_ascii=False)}
Reply ONLY JSON: {{"lines":[{{"n":1,"text":"...","claims":[...],"emotion":"...","role":"..."}}]}}"""
human, m = llm.run('humanizer', p, temperature=0.8, shape='{"lines":[{"n":1,"text":"","claims":[],"emotion":"","role":""}]}')
lines = human['lines']
for a, b in zip(script['lines'], lines):          # humanizer must not change claims or emotion
    b['claims'], b['emotion'], b['role'] = a['claims'], a['emotion'], a.get('role', '')
save('script_humanized.json', {'_llm': m, 'lines': lines, 'pronunciations': script.get('pronunciations', {})})

# 4. hook score
p = f"""{sk('hook-scorer')}
Score ONLY the first line of this reel as the hook. Score each criterion 0, 1 or 2: clarity, curiosity, nepal_relevance, payoff, speakable.
Hook: {lines[0]['text']}
Whole script (to check the hook does not promise more than it delivers): {' | '.join(l['text'] for l in lines)}
Reply ONLY JSON: {{"scores":{{"clarity":0,"curiosity":0,"nepal_relevance":0,"payoff":0,"speakable":0}},"reasons":{{"clarity":"..."}},"misleading":false,"misleading_reason":""}}"""
hook, m = llm.run('hook', p, temperature=0.2, shape='{"scores":{},"reasons":{},"misleading":false}')
hook['_llm'] = m
hook['total'] = sum(hook['scores'].values())
save('hook.json', hook)

# 5. director: popup icons from the licensed list, and the demo plan
p = f"""{sk('icon-motion')}
Allowed popup icon names (only these, they map to Noto Color Emoji, Apache-2.0 / OFL): {', '.join(ICONS['icons'])}.
Pick at most one popup icon per line, only where it helps (leave null otherwise). Do not use more than 4 popups in total.
Script lines: {json.dumps([{'n': l['n'], 'text': l['text']} for l in lines], ensure_ascii=False)}
Reply ONLY JSON: {{"popups":[{{"n":1,"icon":"search"}}]}}"""
plan, m = llm.run('director', p, temperature=0.3, shape='{"popups":[{"n":1,"icon":""}]}')
plan['_llm'] = m
_rec = json.loads((HERE / 'assets/demo/recipes.json').read_text())
plan['demo'] = {'recipe': entry['id'] if entry['id'] in _rec else '_fallback', 'tool': _rec.get(entry['id'], _rec['_fallback'])['tool'],
                'expected': _rec.get(entry['id'], _rec['_fallback'])['expected']}
plan['voice'] = voice_name
plan['popups'] = [x for x in plan.get('popups', []) if x.get('icon') in ICONS['icons']][:4]
save('plan.json', plan)
llm.save_log(out / 'llm_log.json')

# 6. validator (deterministic, fails closed)
sys.path.insert(0, str(HERE / 'validator'))
from validate_draft import validate
v = validate(research, lines, hook, plan, STYLES, ICONS, pages)
save('validation.json', v)
if not v['ok']:
    summary('## Draft REJECTED by the validator. Nothing was sent to the GPU.\n' + '\n'.join('- ' + e for e in v['errors']))
    sys.exit(2)
if llm.FAILOVER_FROM:
    summary(f"## FAILOVER: {llm.FAILOVER_FROM} was unavailable (429/5xx). The WHOLE text sequence ran on {llm.WRITER}. Reviewer is the same model family, so the hook and icon review is NOT independent. Voice is still Gemini TTS.")
summary(f"## Draft passed the validator\nTopic: **{research['topic']}**, hook score {hook['total']}/10, Gemini requests so far: {gemini.COUNT[0]}\n" +
        '\n'.join(f"{l['n']}. [{l['emotion']}] {l['text']}" for l in lines))

# 7. Gemini voice with per-line emotion
if no_voice:
    sys.exit(0)
pron = {**PRON, **script.get('pronunciations', {})}
def fix(t):
    for k, val in sorted(pron.items(), key=lambda kv: -len(kv[0])):
        t = re.sub(r'(?<![A-Za-z])' + re.escape(k) + r'(?![A-Za-z])', val, t)
    return t
for l in lines:
    l['spoken'] = fix(l['text'])
turns = [{'text': l['spoken'], 'emotion': l['emotion'], 'style': STYLES[l['emotion']]} for l in lines]
import os, wave
if os.environ.get('GEMINI_TTS_MODEL') == 'interactions':   # optional newer Gemini 3.x TTS, off by default
    wav, rate = gemini.speech_styled([{'text': t['text'], 'style': t['style']} for t in turns], voice=voice_name)
else:                                                       # default: same approach as the earlier project
    pcm, rate = gemini.speech_km(turns)
    with wave.open(str(out / 'voice.wav'), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)
    wav = (out / 'voice.wav').read_bytes()
(out / 'voice.wav').write_bytes(wav)
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(out / 'voice.wav'), '-ar', '44100', '-b:a', '128k', str(out / 'voice.mp3')], check=True)
dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(out / 'voice.mp3')]).decode())

# estimated word timings: speech span from silencedetect, line boundaries snapped to the longest pauses
sd = subprocess.run(['ffmpeg', '-v', 'info', '-i', str(out / 'voice.wav'), '-af', 'silencedetect=n=-38dB:d=0.18', '-f', 'null', '-'], capture_output=True, text=True).stderr
starts = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', sd)]
ends = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', sd)]
gaps = [(s, e) for s, e in zip(starts, ends) if s > 0.3 and e < dur - 0.1]
t0 = ends[0] if starts and starts[0] < 0.05 and ends else 0.0
t1 = starts[-1] if starts and len(starts) > len(ends) else dur
cuts = None
if len(gaps) >= len(lines) - 1:
    best = sorted(sorted(gaps, key=lambda g: g[0] - g[1])[:len(lines) - 1])
    cuts = [(a + b) / 2 for a, b in best]
bounds = [t0] + (cuts if cuts else []) + [t1]
if not cuts:
    L = [len(l['spoken']) for l in lines]; tot = sum(L); acc = t0; bounds = [t0]
    for n in L:
        acc += (t1 - t0) * n / tot; bounds.append(acc)
words = []
for i, l in enumerate(lines):
    ws = l['spoken'].split(); a, b = bounds[i], bounds[i + 1]
    tot = sum(len(w) + 1 for w in ws); t = a
    for w in ws:
        d = (b - a) * (len(w) + 1) / tot; words.append({'w': w, 'start': round(t, 3), 'end': round(t + d, 3), 'line': l['n']}); t += d
save('words.json', words)
pop = []
for x in plan['popups']:
    ln = [w for w in words if w['line'] == x['n']]
    if ln:
        pop.append({'emoji': ICONS['icons'][x['icon']], 'start': ln[0]['start'], 'end': min(ln[-1]['end'] + 0.3, ln[0]['start'] + 2.5), 'name': x['icon']})
save('icons.json', pop)
save('demo.json', plan['demo'])
summary(f"Voice ready: {dur:.1f}s, voice {voice_name}, line boundaries {'snapped to pauses' if cuts else 'estimated by letter count'}. Gemini requests used: {gemini.COUNT[0]}.")
