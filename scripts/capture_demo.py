#!/usr/bin/env python3
"""Record a public website demo with Playwright and auto-zoom on the actions with Pillow + ffmpeg.

Usage: capture_demo.py OUT.mp4 [--url URL] [--query TEXT]
Output: 1080x960 mp4 (the top panel), 30 fps, silent. Free, no accounts, public page only.
Flow (password topic): Bitwarden strength tester, type a weak password then a strong passphrase, zoom on the verdict. Public page, no account.
"""
import json, subprocess, sys, time, shutil
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image

W, H, FPS = 1080, 960, 30
S = 1.0  # coordinates are already in video pixels; the page itself is enlarged with CSS zoom below
out = sys.argv[1]

work = Path('/tmp/demo_cap'); shutil.rmtree(work, ignore_errors=True); work.mkdir()

CURSOR_JS = """
(() => { const d = document.createElement('div');
 d.style.cssText='position:fixed;z-index:2147483647;width:26px;height:26px;border-radius:50%;background:rgba(255,40,40,.85);border:3px solid #fff;pointer-events:none;left:-50px;top:-50px;transform:translate(-50%,-50%);box-shadow:0 0 8px rgba(0,0,0,.5)';
 document.documentElement.appendChild(d);
 addEventListener('mousemove', e => { d.style.left=e.clientX+'px'; d.style.top=e.clientY+'px'; }, true); })();
"""
recipes = json.loads((Path(__file__).resolve().parent.parent / 'assets/demo/recipes.json').read_text())
rid = sys.argv[sys.argv.index('--recipe') + 1] if '--recipe' in sys.argv else 'passwords'
rec = recipes.get(rid) or recipes['_fallback']
print('recipe', rid if rid in recipes else '_fallback', rec['tool'])
events = []  # (t, x, y, zoom)
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': W, 'height': H}, record_video_dir=str(work), record_video_size={'width': W, 'height': H})
    page = ctx.new_page(); t0 = time.time()
    now = lambda: time.time() - t0
    page.add_init_script(CURSOR_JS)
    hide = ','.join(rec.get('hide') or [])
    if hide:
        page.add_init_script("document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');s.textContent=%s;document.head.appendChild(s)})" % json.dumps(hide + '{display:none!important}'))
    if rec['mode'] == 'cards':
        page.goto((Path(__file__).resolve().parent.parent / rec['file']).as_uri()); page.wait_for_timeout(int(rec.get('seconds', 12)) * 1000)
    else:
        page.goto(rec['url'], wait_until='domcontentloaded'); page.wait_for_timeout(2500)
        if rec.get('reject_cookie'):
            try: page.get_by_role('button', name=rec['reject_cookie']).click(timeout=2500)
            except Exception: pass
        if hide: page.add_style_tag(content=hide + '{display:none!important}')
        if rec.get('scroll_to') and rec['scroll_to'] != 'body':
            page.evaluate("document.querySelector(%s).scrollIntoView({block:'center'})" % json.dumps(rec['scroll_to']))
        page.wait_for_timeout(800)
        events.append((now(), W / 2, H / 2, 1.0))
        def center(sel):
            bb = page.locator(sel).first.bounding_box()
            return (bb['x'] + bb['width'] / 2, bb['y'] + bb['height'] / 2) if bb else (W / 2, H / 2)
        for st in rec['steps']:
            d = st['do']
            if d == 'zoom':
                x, y = center(st['sel']); page.mouse.move(x, y, steps=20); events.append((now(), W / 2, y, st.get('z', 1.4))); page.wait_for_timeout(600)
            elif d == 'wait':
                page.wait_for_timeout(st['ms'])
            elif d == 'type':
                x, y = center(st['sel']); page.mouse.move(x, y, steps=20); page.mouse.click(x, y)
                events.append((now(), st.get('x', W / 2), y + st.get('dy', 60), st.get('z', 1.45)))
                page.keyboard.press('Control+A'); page.keyboard.press('Delete')
                page.keyboard.type(st['text'], delay=70)
                if st.get('enter'): page.keyboard.press('Enter'); page.wait_for_timeout(st.get('after', 2000))
                page.wait_for_timeout(st.get('wait', 1500)); events.append((now(), st.get('x', W / 2), y + st.get('dy', 60) + 50, st.get('z', 1.45))); page.wait_for_timeout(700)
        events.append((now(), W / 2, H / 2, 1.0)); page.wait_for_timeout(500)
    total = now(); ctx.close(); b.close()
vid = next(work.glob('*.webm'))
# the recording starts a bit before t0; align by video duration
vdur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(vid)]).decode())
off = max(0.0, vdur - total)
keys = [(0.0, W / 2, H / 2, 1.0)] + [(t + off, x, y, z) for t, x, y, z in events]
keys.sort()

def ease(u):
    return u * u * (3 - 2 * u)

def cam(t):
    for (ta, xa, ya, za), (tb, xb, yb, zb) in zip(keys, keys[1:]):
        if t <= tb:
            u = ease(min(1, max(0, (t - ta) / max(1e-3, (tb - ta)))))
            return xa + (xb - xa) * u, ya + (ya * 0 + (yb - ya)) * u, za + (zb - za) * u
    return keys[-1][1:]

start = max(0.0, keys[1][0] - 0.1) if rec['mode'] == 'web' and len(keys) > 1 else 0.0
dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-ss', str(start), '-i', str(vid), '-vf', f'fps={FPS},scale={W}:{H}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
enc = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], stdin=subprocess.PIPE)
n = 0
fs = W * H * 3
while True:
    buf = dec.stdout.read(fs)
    if len(buf) < fs:
        break
    t = n / FPS
    x, y, z = cam(t + start)
    cw, ch = W / z, H / z
    x0 = min(max(x - cw / 2, 0), W - cw); y0 = min(max(y - ch / 2, 0), H - ch)
    im = Image.frombytes('RGB', (W, H), buf).resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))
    enc.stdin.write(im.tobytes()); n += 1
enc.stdin.close(); enc.wait(); dec.wait()
print('wrote', out, 'frames', n, 'seconds', round(n / FPS, 2))
