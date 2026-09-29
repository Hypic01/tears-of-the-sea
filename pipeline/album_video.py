"""Finish one album's hero video from its AI clip(s): loop, colour, size, web encodes, posters.

  1. plate_prep.py: join the clip(s) into a loop with no pause, soft frames or stepping
  2. colour: fit the clip's first frame to the still it was generated from, apply to every frame
  3. write the 2560x1440 master (BT.709), crop the tall cut from it (the cover's illustration area)
  4. web encodes (AV1 + H.264) and posters into assets/tapes/<slug>/

usage: python3 album_video.py SLUG ART_X0 CLIP.mp4 [CLIP2.mp4 ...]
  ART_X0 = where the cover's illustration starts in the 2560-wide frame (it is 915 wide, full height)
reads masters/albums/<slug>/wide_still.png
"""
import sys, os, subprocess, json
import cv2
import numpy as np

slug, x0, clips = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
here = os.path.dirname(os.path.abspath(__file__))
src = f'masters/albums/{slug}'; out = f'assets/tapes/{slug}'
os.makedirs(out, exist_ok=True)
subprocess.run(['python3', f'{here}/plate_prep.py', f'{src}/loop.mkv', *clips], check=True)

cap = cv2.VideoCapture(f'{src}/loop.mkv'); F = []
while True:
    ok, f = cap.read()
    if not ok:
        break
    F.append(f)
N = len(F); h, w = F[0].shape[:2]
still = cv2.resize(cv2.imread(f'{src}/wide_still.png'), (w, h), interpolation=cv2.INTER_AREA)
c0 = cv2.VideoCapture(clips[0]); _, first = c0.read()          # the clip's own first frame is the still, as the model saw it


def feats(x):
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    return np.stack([np.ones_like(r), r, g, b, r * r, g * g, b * b, r * g, r * b, g * b], -1)


X = (cv2.GaussianBlur(first, (0, 0), 2).astype(np.float32) / 255).reshape(-1, 3)[:, ::-1]
Y = (cv2.GaussianBlur(still, (0, 0), 2).astype(np.float32) / 255).reshape(-1, 3)[:, ::-1]
idx = np.random.default_rng(0).choice(len(X), 200000, replace=False); X, Y = X[idx], Y[idx]
keep = np.ones(len(X), bool)
for _ in range(4):
    Wt, *_ = np.linalg.lstsq(feats(X[keep]), Y[keep], rcond=None)
    err = np.linalg.norm(feats(X) @ Wt - Y, axis=1); keep = err < np.percentile(err, 85)
print('colour fit: median error %.1f / 255' % (np.median(err) * 255))

X264 = ['-x264-params', 'colorprim=bt709:transfer=bt709:colormatrix=bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-color_range', 'tv']
master = f'{src}/wide_master.mp4'
pipe = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '2560x1440', '-r', '30', '-i', '-',
                         '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p', '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', *X264, '-an', master], stdin=subprocess.PIPE)
rng = np.random.default_rng(11)
grain = [rng.normal(0, 1.2, (720, 1280)).astype(np.float32) for _ in range(12)]
for i, f in enumerate(F):
    g = np.clip(feats(f[..., ::-1].astype(np.float32) / 255) @ Wt, 0, 1)[..., ::-1] * 255
    g = cv2.resize(g, (2560, 1440), interpolation=cv2.INTER_LANCZOS4)
    g += cv2.resize(grain[i % 12], (2560, 1440))[..., None]
    o = np.clip(g, 0, 255).astype(np.uint8)
    if i == 0:
        cv2.imwrite(f'{out}/poster-wide.jpg', o, [cv2.IMWRITE_JPEG_QUALITY, 86])
        cv2.imwrite(f'{out}/poster-tall.jpg', o[:, x0:x0 + 915], [cv2.IMWRITE_JPEG_QUALITY, 86])
    pipe.stdin.write(o.tobytes())
pipe.stdin.close(); pipe.wait()
tall = f'{src}/tall_master.mp4'
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', master, '-vf', f'crop=914:1440:{x0}:0', '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-pix_fmt', 'yuv420p', *X264, '-an', tall], check=True)
for cut, m in (('wide', master), ('tall', tall)):
    r = subprocess.run(['python3', f'{here}/web_encode.py', m, f'{out}/hero-{cut}', '13.5'], capture_output=True, text=True)
    print(cut, [l for l in r.stdout.splitlines() if l[:3] in ('av1', 'h26')][-2:])
p = f'data/tapes/{slug}.json'; d = json.load(open(p))
d['video'] = dict(frames=N, a0=round(x0 / 2560, 4), v=1); json.dump(d, open(p, 'w'), indent=1, ensure_ascii=False)
print('done', slug, N, 'frames', round(N / 30, 1), 's')
