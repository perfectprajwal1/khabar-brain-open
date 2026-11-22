#!/usr/bin/env python3
"""Zero-Gemini stand-in for brain.py, for testing the chain plumbing only.
Fetches the real source-pack pages, uses real sentences from them as quotes, runs the real validator,
writes a canned Nepali script and reuses assets/face/voice_test6.mp3 as the voice. Makes no Gemini request.
Output files match brain.py. Everything here is a FIXTURE, not a real draft."""
import json, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sourcepack
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / 'validator'))
from validate_draft import validate
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
STYLES = json.loads((HERE / 'assets/voice/styles.json').read_text()); STYLES.pop('_note', None)
ICONS = json.loads((HERE / 'assets/icons.json').read_text())
entry = json.loads((HERE / 'assets/source_pack.json').read_text())['topics'][0]
pages = sourcepack.fetch_topic(entry)
claims = [{'id': f'c{i+1}', 'text': 'FIXTURE claim', 'sources': [{'publisher': p['publisher'], 'url': p['url'], 'quote': p['text'][i * 60 + (0 if p['text'][i * 60 - 1:i * 60] in ('', ' ') else p['text'][i * 60:].find(' ') + 1):][:90].strip()} for p in pages]} for i in range(3)]
research = {'topic': entry['topic'] + ' (FIXTURE)', 'claims': claims, 'demo_query': entry['demo_query']}
L = [('के तपाईंको खाता साँच्चै सुरक्षित छ?', [], 'curious', 'hook'), ('एउटा सानो कदमले तपाईंको अनलाइन खातामा धेरै ठूलो फरक पार्न सक्छ।', ['c1'], 'hopeful', 'body'),
     ('अब पासवर्डसँगै फोनमा आउने अर्को कोड पनि चाहिन्छ, अनि मात्र खाता खुल्छ।', ['c2'], 'serious', 'body'), ('यसरी कसैले पासवर्ड थाहा पाए पनि तपाईंको खातामा सजिलै पस्न सक्दैन।', ['c3'], 'confident', 'body'),
     ('आजै अन गर्नुहोस्, पाँच मिनेट मात्र लाग्छ।', [], 'encouraging', 'takeaway')]
lines = [{'n': i + 1, 'text': t, 'claims': c, 'emotion': e, 'role': r} for i, (t, c, e, r) in enumerate(L)]
hook = {'scores': {'clarity': 2, 'curiosity': 2, 'nepal_relevance': 1, 'payoff': 1, 'speakable': 2}, 'total': 8, 'misleading': False}
plan = {'popups': [{'n': 1, 'icon': 'lock'}, {'n': 4, 'icon': 'check'}], 'demo': {'recipe': entry['id']}, 'voice': 'FIXTURE (voice_test6.mp3)'}
v = validate(research, lines, hook, plan, STYLES, ICONS, pages)
sv = lambda n, o: (out / n).write_text(json.dumps(o, ensure_ascii=False, indent=2), encoding='utf-8')
sv('research.json', research); sv('script_humanized.json', {'lines': lines}); sv('hook.json', hook); sv('plan.json', plan); sv('validation.json', v); sv('demo.json', plan['demo'])
mp3 = out / 'voice.mp3'; subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(HERE / 'assets/face/voice_test6.mp3'), str(mp3)], check=True)
dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(mp3)]).decode())
words, t, tot = [], 0.3, sum(len(l['text']) for l in lines)
for l in lines:
    ws = l['text'].split(); span = (dur - 0.6) * len(l['text']) / tot; ch = sum(len(w) + 1 for w in ws); a = t
    for w in ws:
        d = span * (len(w) + 1) / ch; words.append({'w': w, 'start': round(t, 3), 'end': round(t + d, 3), 'line': l['n']}); t += d
sv('words.json', words)
sv('icons.json', [{'emoji': ICONS['icons'][x['icon']], 'start': [w for w in words if w['line'] == x['n']][0]['start'], 'end': [w for w in words if w['line'] == x['n']][0]['start'] + 2.0} for x in plan['popups']])
print('FIXTURE written. validator ok =', v['ok'], v['errors'], flush=True)
sys.exit(0 if v['ok'] else 2)
