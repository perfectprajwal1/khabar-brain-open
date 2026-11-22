#!/usr/bin/env python3
"""Join a top-half content clip and a bottom-half lip-sync face clip into a 1080x1920 reel.

Usage: compose_split.py TOP.mp4 FACE.mp4 VOICE.mp3 CAPTION_TEXT OUT.mp4 [--words words.json] [--icons icons.json]
icons.json: [{"emoji": "🔍", "start": 1.0, "end": 2.5}] popup icons on the top panel (Noto Color Emoji, font path from env EMOJI_FONT).
Layout: top 1080x960 content, bottom 1080x960 face. One caption line on the seam,
Noto Sans Devanagari Bold, white words with the current spoken word in red.
words.json: [{"w": "word", "start": 0.0, "end": 0.4}, ...] from real word timings.
Without it, timings are split by word length across the voice length (approximate).
The top clip loops to the voice length. Audio is the voice only.
"""
import json, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, features

W, H = 1080, 1920
HERE = Path(__file__).resolve().parent.parent
skipv = {sys.argv[i + 1] for i, a in enumerate(sys.argv) if a in ('--words', '--icons') and i + 1 < len(sys.argv)}
args = [a for a in sys.argv[1:] if not a.startswith('--') and a not in skipv]
top, face, voice, caption, out = args[:5]
words_file = sys.argv[sys.argv.index('--words') + 1] if '--words' in sys.argv else None
icons_file = sys.argv[sys.argv.index('--icons') + 1] if '--icons' in sys.argv else None
if not features.check('raqm'):
    print('WARNING: Pillow has no raqm, Devanagari shaping may be wrong', flush=True)

dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', voice]).decode().strip())
if words_file:
    items = json.load(open(words_file))
else:
    ws = caption.split()
    tot = sum(len(w) + 1 for w in ws)
    items, t = [], 0.0
    for w in ws:
        d = dur * (len(w) + 1) / tot
        items.append({'w': w, 'start': t, 'end': t + d})
        t += d

font = ImageFont.truetype(str(HERE / 'assets/fonts/NotoSansDevanagari-Bold.ttf'), 92)
probe = ImageDraw.Draw(Image.new('RGBA', (10, 10)))
MAXW = W - 90
SP = probe.textlength(' ', font=font)


def width(ws):
    return sum(probe.textlength(x['w'], font=font) for x in ws) + SP * (len(ws) - 1)

# group words into one-line chunks that fit the width
chunks, cur = [], []
for it in items:
    if cur and width(cur + [it]) > MAXW:
        chunks.append(cur); cur = []
    cur.append(it)
if cur:
    chunks.append(cur)

frames = []  # (png, start, end)
n = 0
for ch in chunks:
    for k, active in enumerate(ch):
        img = Image.new('RGBA', (W, 220), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        x = (W - width(ch)) / 2
        for it in ch:
            col = (255, 40, 40, 255) if it is active else (255, 255, 255, 255)
            dr.text((x, 40), it['w'], font=font, fill=col, stroke_width=9, stroke_fill=(0, 0, 0, 255))
            x += probe.textlength(it['w'], font=font) + SP
        p = f'/tmp/cap_{n:03d}.png'
        img.save(p)
        start = active['start']
        # hold until next word starts (or chunk end) so there are no flicker gaps
        nxt = ch[k + 1]['start'] if k + 1 < len(ch) else active['end']
        frames.append((p, start, nxt))
        n += 1

popups = []
if icons_file:
    import os
    try:
        efont = ImageFont.truetype(os.environ.get('EMOJI_FONT', '/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf'), 109)
    except OSError:
        efont = None   # emoji font only needed when a Tabler PNG is missing for an icon name
    for k, ic in enumerate(json.load(open(icons_file))):
        tp = Path(__file__).resolve().parent.parent / 'assets/icons/tabler' / (str(ic.get('name', '')) + '.png')
        if tp.exists():      # Tabler Icons (MIT), outline, one brand colour (yellow) so every popup matches
            a = Image.open(tp).convert('RGBA').split()[3].resize((176, 176), Image.LANCZOS)
            im = Image.new('RGBA', (200, 188), (0, 0, 0, 0)); col = Image.new('RGBA', (176, 176), (250, 204, 21, 255)); col.putalpha(a)
            im.alpha_composite(col, (12, 6))
        else:
            if efont is None:
                continue
            im = Image.new('RGBA', (136, 128), (0, 0, 0, 0))
            ImageDraw.Draw(im).text((0, 0), ic['emoji'], font=efont, embedded_color=True)
            im = im.resize((200, 188), Image.LANCZOS)
        bg = Image.new('RGBA', (240, 228), (0, 0, 0, 0))
        ImageDraw.Draw(bg).rounded_rectangle((0, 0, 239, 227), 48, fill=(0, 0, 0, 150))
        bg.alpha_composite(im, (20, 20))
        pp = f'/tmp/icon_{k:02d}.png'; bg.save(pp); popups.append((pp, ic['start'], ic['end']))
inputs = ['-stream_loop', '-1', '-i', top, '-i', face, '-i', voice]
for p, _, _ in frames + popups:
    inputs += ['-loop', '1', '-i', p]
fc = ('[0:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960,fps=30,setsar=1[t];'
      '[1:v]scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:960:0:40,fps=30,setsar=1[f];'
      '[t][f]vstack=inputs=2[s0];')
prev = 's0'
for i, (p, a, b) in enumerate(frames):
    nxt = f's{i+1}'
    fc += f'[{prev}][{3+i}:v]overlay=0:{H//2-90}:enable=\'between(t,{a:.3f},{b:.3f})\':format=auto[{nxt}];'
    prev = nxt
for j, (pp, a, b) in enumerate(popups):
    nxt = f'p{j+1}'
    fc += f"[{prev}][{3+len(frames)+j}:v]overlay={W-270}:40:enable='between(t,{a:.3f},{b:.3f})':format=auto[{nxt}];"
    prev = nxt
fc += f'[{prev}]format=yuv420p[v]'
cmd = ['ffmpeg', '-y', '-v', 'error', *inputs, '-filter_complex', fc, '-map', '[v]', '-map', '2:a',
       '-t', f'{dur:.3f}', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-c:a', 'aac',
       '-ar', '48000', '-ac', '2', '-movflags', '+faststart', out]
subprocess.run(cmd, check=True)
print('wrote', out, 'chunks', len(chunks), 'words', len(items))
