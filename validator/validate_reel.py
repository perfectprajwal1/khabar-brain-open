#!/usr/bin/env python3
"""Final-MP4 validator for khabar-brain. No model calls, no network. Fails closed on hard errors, warns on soft ones.
Usage: validate_reel.py REEL.mp4 [--voice voice.mp3] [--out report.json] [--min-seconds 12]
Hard errors: wrong streams/size/fps, duration outside 12-60 s or far from the voice length, no audio, long silence,
black frames, frozen frames (whole 1080x1920 frame static for 3 s or more).
Warnings (approximate, pixel based, red current-word only): red caption pixels in the outer 30 px of the caption band (safe area).
It cannot judge Nepali quality, voice quality or whether the demo matches the words. A human still watches the reel."""
import json, re, subprocess, sys, warnings
warnings.filterwarnings('ignore')
from pathlib import Path


def sh(*a):
    r = subprocess.run(a, capture_output=True, text=True)
    return r.stdout + r.stderr


def dur(p):
    return float(sh('ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p).strip().splitlines()[0])


def main():
    reel = sys.argv[1]
    voice = sys.argv[sys.argv.index('--voice') + 1] if '--voice' in sys.argv else None
    outp = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else None
    E, W = [], []
    lo = float(sys.argv[sys.argv.index('--min-seconds') + 1]) if '--min-seconds' in sys.argv else 12.0
    if not Path(reel).exists():
        print(json.dumps({'pass': False, 'errors': ['file not found: ' + reel]})); sys.exit(2)
    info = json.loads(sh('ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', reel))
    vs = [s for s in info['streams'] if s['codec_type'] == 'video']
    au = [s for s in info['streams'] if s['codec_type'] == 'audio']
    if len(vs) != 1: E.append(f'expected 1 video stream, got {len(vs)}')
    if len(au) != 1: E.append(f'expected 1 audio stream, got {len(au)}')
    d = float(info['format']['duration'])
    if vs:
        v = vs[0]
        if (v['width'], v['height']) != (1080, 1920): E.append(f"size {v['width']}x{v['height']}, expected 1080x1920")
        n, m = (v['r_frame_rate'].split('/') + ['1'])[:2]
        fps = float(n) / float(m or 1)
        if not (24 <= fps <= 60): E.append(f'frame rate {fps}')
        if v.get('codec_name') != 'h264': W.append(f"video codec {v.get('codec_name')}, h264 is safest for upload")
    if not (lo <= d <= 60): E.append(f'duration {d:.1f}s outside {lo:g} to 60 s')
    if voice:
        vd = dur(voice)
        if abs(d - vd) > 1.5: E.append(f'reel {d:.1f}s vs voice {vd:.1f}s differ by more than 1.5 s')
    if au:
        log = sh('ffmpeg', '-v', 'info', '-i', reel, '-af', 'silencedetect=noise=-45dB:d=2.5', '-vn', '-f', 'null', '-')
        sil = re.findall(r'silence_duration: ([\d.]+)', log)
        if sil: E.append(f'silence of {max(map(float, sil)):.1f}s inside the reel (limit 2.5 s)')
        vol = sh('ffmpeg', '-v', 'info', '-i', reel, '-af', 'volumedetect', '-vn', '-f', 'null', '-')
        mm = re.search(r'max_volume: (-?[\d.]+) dB', vol)
        if mm and float(mm.group(1)) < -30: E.append(f'audio far too quiet, max {mm.group(1)} dB')
    log = sh('ffmpeg', '-v', 'info', '-i', reel, '-vf', 'blackdetect=d=0.5:pix_th=0.10,freezedetect=n=-60dB:d=3', '-an', '-f', 'null', '-')
    if re.search(r'black_start', log): E.append('black frames for 0.5 s or more')
    fz = re.findall(r'freeze_duration: ([\d.]+)', log)
    if fz: E.append(f'whole frame frozen for {max(map(float, fz)):.1f}s (limit 3 s)')
    # caption safe area (approximate): text-coloured pixels hugging the left/right edge of the caption band
    try:
        from PIL import Image
        import io
        hits = 0
        for t in [d * k / 6 for k in range(1, 6)]:
            png = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.2f}', '-i', reel, '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True).stdout
            im = Image.open(io.BytesIO(png)).convert('RGB')
            for x0, x1 in ((0, 30), (1050, 1080)):
                strip = im.crop((x0, 880, x1, 1040)).getdata()
                hits += sum(1 for r, g, b in strip if r > 210 and g < 70 and b < 70)
        if hits > 150: W.append(f'caption band has {hits} red caption pixels in the outer 30 px (possible clipped caption), check by eye')
    except Exception as e:
        W.append('caption safe-area check skipped: ' + type(e).__name__)
    rep = {'file': Path(reel).name, 'duration_s': round(d, 2), 'errors': E, 'warnings': W, 'pass': not E}
    print(json.dumps(rep, indent=1))
    if outp: Path(outp).write_text(json.dumps(rep, indent=1))
    sys.exit(0 if not E else 2)


main()
