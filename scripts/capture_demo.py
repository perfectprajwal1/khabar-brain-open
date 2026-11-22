#!/usr/bin/env python3
"""Record a public website demo with Playwright and auto-zoom on the actions with Pillow + ffmpeg.

Usage: capture_demo.py OUT.mp4 [--url URL] [--query TEXT]
Output: 1080x960 mp4 (the top panel), 30 fps, silent. Free, no accounts, public page only.
Flow: open page, click the search box (zoom in), type the query, press Enter, scroll the results.
"""
import json, subprocess, sys, time, shutil
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image

W, H, FPS = 1080, 960, 30
S = 1.0  # coordinates are already in video pixels; the page itself is enlarged with CSS zoom below
out = sys.argv[1]
url = sys.argv[sys.argv.index('--url') + 1] if '--url' in sys.argv else 'https://en.wikipedia.org/wiki/Special:Search'
query = sys.argv[sys.argv.index('--query') + 1] if '--query' in sys.argv else 'How to learn programming'
work = Path('/tmp/demo_cap'); shutil.rmtree(work, ignore_errors=True); work.mkdir()

CURSOR_JS = """
(() => { const d = document.createElement('div');
 d.style.cssText='position:fixed;z-index:2147483647;width:26px;height:26px;border-radius:50%;background:rgba(255,40,40,.85);border:3px solid #fff;pointer-events:none;left:-50px;top:-50px;transform:translate(-50%,-50%);box-shadow:0 0 8px rgba(0,0,0,.5)';
 document.documentElement.appendChild(d);
 addEventListener('mousemove', e => { d.style.left=e.clientX+'px'; d.style.top=e.clientY+'px'; }, true); })();
"""
events = []  # (t, x, y, zoom)
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': W, 'height': H}, record_video_dir=str(work), record_video_size={'width': W, 'height': H})
    page = ctx.new_page(); t0 = time.time()
    now = lambda: time.time() - t0
    page.add_init_script(CURSOR_JS)
    page.add_init_script("document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');s.textContent='html{zoom:1.7}';document.head.appendChild(s)})")
    page.goto(url, wait_until='domcontentloaded'); page.wait_for_timeout(1200)
    box = page.locator('input[type=search]:visible').last
    bb = box.bounding_box(); cx, cy = bb['x'] + min(bb['width'] / 2, 330), bb['y'] + bb['height'] / 2
    page.mouse.move(cx - 300, cy + 200); page.wait_for_timeout(300)
    events.append((now(), cx * S, cy * S, 1.0))
    page.mouse.move(cx, cy, steps=25); events.append((now(), cx * S, cy * S, 1.5))
    page.wait_for_timeout(500); page.mouse.click(cx, cy); page.wait_for_timeout(400)
    page.keyboard.type(query, delay=90); events.append((now(), cx * S, cy * S, 1.5))
    page.keyboard.press('Enter'); page.wait_for_load_state('domcontentloaded'); page.wait_for_timeout(900)
    events.append((now(), W / 2, 330, 1.0)); page.wait_for_timeout(500)
    first = page.locator('.mw-search-result-heading a').first
    fb = first.bounding_box()
    if fb:
        fx, fy = fb['x'] + 160, fb['y'] + fb['height'] / 2
        page.mouse.move(fx, fy, steps=25); events.append((now(), fx * S, fy * S, 1.4)); page.wait_for_timeout(1200)
    events.append((now(), W / 2, H / 2, 1.0)); page.wait_for_timeout(700)
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

dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(vid), '-vf', f'fps={FPS},scale={W}:{H}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
enc = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], stdin=subprocess.PIPE)
n = 0
fs = W * H * 3
while True:
    buf = dec.stdout.read(fs)
    if len(buf) < fs:
        break
    t = n / FPS
    x, y, z = cam(t)
    cw, ch = W / z, H / z
    x0 = min(max(x - cw / 2, 0), W - cw); y0 = min(max(y - ch / 2, 0), H - ch)
    im = Image.frombytes('RGB', (W, H), buf).resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))
    enc.stdin.write(im.tobytes()); n += 1
enc.stdin.close(); enc.wait(); dec.wait()
print('wrote', out, 'frames', n, 'seconds', round(n / FPS, 2))
