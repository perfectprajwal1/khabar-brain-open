#!/usr/bin/env python3
"""Run the SoulX-FlashHead lip-sync notebook on the owner's free Kaggle GPU.

Usage: kaggle_lipsync.py PHOTO AUDIO OUTDIR [--max-wait-min 75] [--collect]
  --collect: do not push. Only download the result of the session already running or done.
Needs env KAGGLE_API_TOKEN and the `kaggle` CLI (2.x). One job at a time:
refuses to start if the kernel is already queued or running. Stops on any
error. Never retries a push.
Cancel-safe: a wait timeout or a cancel/SIGTERM exits cleanly (exit 0 / 3), says in the
job summary that the Kaggle session may still be queued and is NOT lost, and
`--collect` (or the collect workflow) can fetch its result later without a new push.
Exit codes: 0 done or still pending (see output done=true/false), 1 failed, 3 cancelled.
"""
import base64, json, os, shutil, signal, subprocess, sys, tempfile, time
from pathlib import Path

SLUG = os.environ.get('KAGGLE_KERNEL_SLUG', 'YOUR_KAGGLE_USER/khabar-brain-lipsync')
HERE = Path(__file__).resolve().parent.parent


def kg(*args, check=True):
    r = subprocess.run(['kaggle', *args], capture_output=True, text=True)
    out = (r.stdout or '') + (r.stderr or '')
    if check and r.returncode != 0:
        print('kaggle', ' '.join(args), 'failed:\n', out[-1500:], flush=True)
        sys.exit(1)
    return out


def gh_out(done):
    f = os.environ.get('GITHUB_OUTPUT')
    if f:
        open(f, 'a').write(f'done={"true" if done else "false"}\n')


def note(text):
    print(text, flush=True)
    f = os.environ.get('GITHUB_STEP_SUMMARY')
    if f:
        open(f, 'a').write(text + '\n')


def on_signal(signum, frame):
    gh_out(False)
    note(f'Run was cancelled (signal {signum}). The Kaggle session `{SLUG}` may STILL be queued or running and is not lost. '
         f'Check https://www.kaggle.com/code/{SLUG} . Fetch its result later with the collect workflow, do not start a second job.')
    sys.exit(3)


def status():
    out = kg('kernels', 'status', SLUG, check=False)
    for s in ('QUEUED', 'RUNNING', 'COMPLETE', 'ERROR', 'CANCEL'):
        if 'KernelWorkerStatus.' + s in out:
            return s
    return 'NONE' if ('Cannot access kernel' in out or '404' in out or 'Not Found' in out) else 'UNKNOWN:' + out.strip()[-200:]


def finish(outdir):
    Path(outdir).mkdir(parents=True, exist_ok=True)
    print(kg('kernels', 'output', SLUG, '-p', outdir, '--file-pattern', r'lipsync\.mp4$'), flush=True)
    mp4 = Path(outdir) / 'lipsync.mp4'
    if not mp4.exists() or mp4.stat().st_size < 10000:
        print('No lipsync.mp4 in output:', list(Path(outdir).iterdir()))
        sys.exit(1)
    gh_out(True)
    print('OK', mp4, mp4.stat().st_size)


def main():
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    gh_out(False)
    photo, audio, outdir = sys.argv[1:4]
    if '--collect' in sys.argv:
        st = status()
        print('collect: kernel status', st, flush=True)
        if st == 'COMPLETE':
            finish(outdir)
            return
        if st in ('QUEUED', 'RUNNING'):
            note(f'Kaggle session `{SLUG}` is still {st}. Nothing downloaded yet. Run collect again later.')
            return
        note(f'Kaggle session ended as {st}. Check the logs on Kaggle.')
        sys.exit(1)
    max_wait = 75
    if '--max-wait-min' in sys.argv:
        max_wait = int(sys.argv[sys.argv.index('--max-wait-min') + 1])
    st = status()
    print('kernel status before push:', st, flush=True)
    if st in ('QUEUED', 'RUNNING'):
        print('A lip-sync job is already active. Not starting a second one.')
        sys.exit(1)
    if st.startswith('UNKNOWN'):
        print('Could not read kernel status, stopping.')
        sys.exit(1)
    tpl = (HERE / 'kaggle' / 'lipsync_template.py').read_text()
    code = tpl.replace('@@PHOTO@@', base64.b64encode(Path(photo).read_bytes()).decode()) \
              .replace('@@AUDIO@@', base64.b64encode(Path(audio).read_bytes()).decode())
    d = Path(tempfile.mkdtemp())
    (d / 'khabar-brain-lipsync.py').write_text(code)
    (d / 'kernel-metadata.json').write_text(json.dumps({
        'id': SLUG, 'title': 'khabar-brain-lipsync',
        'code_file': 'khabar-brain-lipsync.py', 'language': 'python',
        'kernel_type': 'script', 'is_private': True, 'enable_gpu': True,
        'enable_internet': True, 'dataset_sources': [], 'kernel_sources': [],
        'competition_sources': [], 'model_sources': []}, indent=2))
    print(kg('kernels', 'push', '-p', str(d)), flush=True)
    t0 = time.time()
    last = ''
    while True:
        time.sleep(60)
        st = status()
        if st != last:
            print(f'[{int((time.time()-t0)/60)} min] status: {st}', flush=True)
            last = st
        if st == 'COMPLETE':
            break
        if st in ('ERROR', 'CANCEL') or st.startswith('UNKNOWN'):
            print(kg('kernels', 'logs', SLUG, check=False)[-3000:])
            sys.exit(1)
        if time.time() - t0 > max_wait * 60:
            note(f'Stopped waiting after {max_wait} min, Kaggle status is still {st}. The session `{SLUG}` is NOT cancelled and is not lost: https://www.kaggle.com/code/{SLUG} . '
                 'Run the collect workflow later to download the result. Do not start a second job.')
            return
    finish(outdir)


main()
