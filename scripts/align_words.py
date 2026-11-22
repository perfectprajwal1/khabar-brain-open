#!/usr/bin/env python3
"""Real word timing for captions. Free, CPU only, no API calls.
Usage: align_words.py VOICE.mp3 words.json OUT.json [--model small]
Runs faster-whisper (MIT) with word timestamps on the voice, then maps each SCRIPT word to a heard word with a monotonic
alignment on character similarity, and interpolates the words that found no match. Caption text always stays the script text.
Fallback: if the heard word count is not within 25 percent of the script, or fewer than 45 percent of script words match,
OUT.json is the unchanged estimate and the report says method=estimate (flagged). Whisper's Nepali spelling is poor; only its timing is used."""
import json, sys, difflib, re, subprocess
from pathlib import Path

voice, inp, outp = sys.argv[1:4]
model = sys.argv[sys.argv.index('--model') + 1] if '--model' in sys.argv else 'small'
est = json.loads(Path(inp).read_text())
rep = {'method': 'estimate', 'model': model, 'script_words': len(est)}


def fallback(why):
    rep['why'] = why
    Path(outp).write_text(json.dumps(est, ensure_ascii=False, indent=1))
    Path(outp).with_name('align_report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    print('ALIGN FALLBACK to estimated timing:', why)
    sys.exit(0)


try:
    from faster_whisper import WhisperModel
    seg, _ = WhisperModel(model, device='cpu', compute_type='int8').transcribe(voice, language='ne', word_timestamps=True, beam_size=5)
    heard = [(w.word.strip(), w.start, w.end) for s in seg for w in s.words if w.word.strip()]
except Exception as e:
    fallback('faster-whisper failed: ' + type(e).__name__)
rep['heard_words'] = len(heard)
n, m = len(est), len(heard)
if m == 0 or abs(m - n) > 0.25 * n:
    fallback(f'heard {m} words vs script {n}')

def sim(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()

# monotonic alignment (Needleman-Wunsch), match score = similarity - 0.35, gaps cost -0.3
S = [[sim(est[i]['w'].strip('?.,!।'), heard[j][0].strip('?.,!।')) - 0.35 for j in range(m)] for i in range(n)]
G = -0.3
D = [[0.0] * (m + 1) for _ in range(n + 1)]
for i in range(1, n + 1): D[i][0] = i * G
for j in range(1, m + 1): D[0][j] = j * G
for i in range(1, n + 1):
    for j in range(1, m + 1):
        D[i][j] = max(D[i - 1][j - 1] + S[i - 1][j - 1], D[i - 1][j] + G, D[i][j - 1] + G)
i, j, pair = n, m, {}
while i > 0 and j > 0:
    if abs(D[i][j] - (D[i - 1][j - 1] + S[i - 1][j - 1])) < 1e-9:
        if S[i - 1][j - 1] > 0.05: pair[i - 1] = j - 1
        i -= 1; j -= 1
    elif abs(D[i][j] - (D[i - 1][j] + G)) < 1e-9: i -= 1
    else: j -= 1
rep['matched'] = len(pair)
if len(pair) < 0.45 * n:
    fallback(f'only {len(pair)} of {n} script words matched a heard word')
t_end = max(h[2] for h in heard)
st = {k: heard[v][1] for k, v in pair.items()}
# interpolate unmatched starts between matched anchors
anchors = [(-1, 0.0)] + sorted(st.items()) + [(n, t_end)]
start = [0.0] * n
for k, v in st.items(): start[k] = v
for (a, ta), (b, tb) in zip(anchors, anchors[1:]):
    for k in range(a + 1, b):
        if k not in st: start[k] = ta + (tb - ta) * (k - a) / (b - a)
# Whisper often starts a word inside the pause before it. Snap a word start that lies in (or up to 1 s before the end of) a real pause
# to the end of that pause, measured from the audio itself (silencedetect), so captions never run ahead of the voice.
log = subprocess.run(['ffmpeg', '-v', 'info', '-i', voice, '-af', 'silencedetect=noise=-32dB:d=0.12', '-f', 'null', '-'], capture_output=True, text=True).stderr
sil = list(zip([float(x) for x in re.findall(r'silence_start: ([\d.]+)', log)], [float(x) for x in re.findall(r'silence_end: ([\d.]+)', log)]))
snapped = 0
for k in range(1, n):
    for a, b in sil:
        if a - 0.05 <= start[k] <= b and b - start[k] <= 1.0 and b - a >= 0.3:
            start[k] = b; snapped += 1; break
rep['snapped_to_pauses'] = snapped
out = []
for k, w in enumerate(est):
    e = start[k + 1] if k + 1 < n else t_end
    out.append({**w, 'start': round(start[k], 3), 'end': round(max(e, start[k] + 0.12), 3)})
diffs = [abs(o['start'] - w['start']) for o, w in zip(out, est)]
rep.update({'method': 'whisper', 'mean_shift_vs_estimate_s': round(sum(diffs) / n, 2), 'max_shift_vs_estimate_s': round(max(diffs), 2)})
Path(outp).write_text(json.dumps(out, ensure_ascii=False, indent=1))
Path(outp).with_name('align_report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1))
print(json.dumps(rep, ensure_ascii=False))
