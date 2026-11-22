import base64, os, subprocess, sys

PHOTO_B64 = "@@PHOTO@@"
AUDIO_B64 = "@@AUDIO@@"

def sh(c, check=True):
    print('+', c.split(' --')[0][:160], flush=True)
    r = subprocess.run(c, shell=True, capture_output=True, text=True)
    print((r.stdout or '')[-2500:], flush=True)
    if r.returncode != 0:
        print('STDERR:', (r.stderr or '')[-2500:], flush=True)
        if check:
            sys.exit(1)
    return r

W = '/kaggle/working'
open(W + '/photo.jpg', 'wb').write(base64.b64decode(PHOTO_B64))
open(W + '/voice.mp3', 'wb').write(base64.b64decode(AUDIO_B64))
sh('nvidia-smi | head -12', check=False)
sh('ffmpeg -y -v error -i ' + W + '/voice.mp3 -ar 16000 -ac 1 ' + W + '/voice16k.wav && ffprobe -v error -show_entries format=duration -of csv=p=0 ' + W + '/voice16k.wav')
sh('git clone --depth 1 -q https://github.com/Soul-AILab/SoulX-FlashHead ' + W + '/fh && echo CLONED')
os.chdir(W + '/fh')
sh('pip install -q diffusers "transformers==4.57.3" accelerate easydict ftfy imageio imageio-ffmpeg scikit-image loguru pyloudnorm 2>&1 | tail -2')
sh('pip install -q "mediapipe==0.10.35" 2>&1 | tail -2', check=False)
sh('pip install -q decord 2>&1 | tail -2', check=False)
sh('pip install -q "xfuser>=0.4.3" 2>&1 | tail -3')
sh('python -c "from huggingface_hub import snapshot_download; snapshot_download(\'Soul-AILab/SoulX-FlashHead-1_3B\', local_dir=\'models/SoulX-FlashHead-1_3B\')" 2>&1 | tail -3')
sh('python -c "from huggingface_hub import snapshot_download; snapshot_download(\'facebook/wav2vec2-base-960h\', local_dir=\'models/wav2vec2-base-960h\')" 2>&1 | tail -3')
r = sh('python generate_video.py --ckpt_dir models/SoulX-FlashHead-1_3B --wav2vec_dir models/wav2vec2-base-960h --model_type lite --cond_image ' + W + '/photo.jpg --audio_path ' + W + '/voice16k.wav --save_file ' + W + '/lipsync.mp4 --use_face_crop True', check=False)
sh('ls -la ' + W + '/*.mp4', check=False)
print('KERNEL_DONE rc=' + str(r.returncode), flush=True)
sys.exit(r.returncode)
