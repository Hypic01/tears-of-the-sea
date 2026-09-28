"""Gentle underwater hair sway, loop-exact.

Dark hair pixels (minus eyes/lashes and anything near a koi) get a slow travelling-wave displacement,
strongest at the hair tips far from the face and fading to a whisper at the crown. Both wave periods
divide the loop length, so the last frame flows straight into the first.

usage: python3 hair_sway.py IN.mp4 OUT.mp4 wide|tall [amp_px_at_1440=6] [sheet]
"""
import sys, subprocess
import cv2
import numpy as np

src, dst, kind = sys.argv[1], sys.argv[2], sys.argv[3]
AMP = float(sys.argv[4]) if len(sys.argv) > 4 else 6.0
sheet = 'sheet' in sys.argv[5:]

cap = cv2.VideoCapture(src)
fps = cap.get(cv2.CAP_PROP_FPS) or 30
W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

# geometry defined on the 2560x1440 wide frame; the tall portrait maps into it at x=873, scale 0.75
if kind == 'wide':
    s = H / 1440.0
    to = lambda x, y: (x * s, y * s)
else:
    s = 1 / 0.75 * (H / 1920.0)
    to = lambda x, y: ((x - 873) / 0.75 * (H / 1920.0), y / 0.75 * (H / 1920.0))
eyes = [(to(1040, 560), (270 * s, 160 * s)), (to(1560, 545), (270 * s, 160 * s))]
fc = np.array(to(1300, 700))

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
eye_keep = np.ones((H, W), np.float32)
for (cx, cy), (ax, ay) in eyes:
    m = np.zeros((H, W), np.uint8)
    cv2.ellipse(m, (int(cx), int(cy)), (int(ax), int(ay)), 0, 0, 360, 255, -1)
    eye_keep *= 1 - cv2.GaussianBlur(m.astype(np.float32) / 255, (0, 0), 25 * s)
r = np.hypot(xx - fc[0], (yy - fc[1]) * 1.15)
reach = np.clip((r - 380 * s) / (700 * s), 0.2, 1.0)          # crown barely moves, tips drift most
T1, T2, T3 = N / 2.0, N / 3.0, N / 4.0


def hair_mask(f):
    h = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
    dark = (h[..., 2] < 95).astype(np.uint8)
    koi = (((h[..., 0] < 22) | (h[..., 0] > 168)) & (h[..., 1] > 140) & (h[..., 2] > 110)).astype(np.uint8)
    koi = cv2.dilate(koi, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(95 * s) | 1, int(95 * s) | 1)))
    m = cv2.morphologyEx(dark * (1 - koi), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)).astype(np.float32)
    m = cv2.dilate(m, np.ones((int(9 * s) | 1, int(9 * s) | 1), np.uint8))
    return cv2.GaussianBlur(m, (0, 0), 20 * s) * eye_keep


def sway(f, i):
    a = AMP * s * reach * hair_mask(f)
    p1 = 2 * np.pi * i / T1
    p2 = 2 * np.pi * i / T2
    p3 = 2 * np.pi * i / T3
    # three slow currents; phases travel down the strands so waves ripple along the hair like in water
    dx = a * (0.58 * np.sin(p1 - yy / (300 * s) + xx / (1100 * s)) + 0.30 * np.sin(p2 - yy / (170 * s) - xx / (700 * s) + 0.7)
              + 0.14 * np.sin(p3 - yy / (110 * s) + 1.9))
    dy = a * 0.42 * (np.sin(p1 + xx / (380 * s) + 1.3) + 0.4 * np.sin(p2 - yy / (200 * s) + 0.4))
    return cv2.remap(f, (xx - dx).astype(np.float32), (yy - dy).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


if not sheet:
    pipe = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', f'{fps}',
                             '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-pix_fmt', 'yuv420p', '-an', dst], stdin=subprocess.PIPE)
shots = []
i = 0
while True:
    ok, f = cap.read()
    if not ok:
        break
    g = sway(f, i)
    if sheet and i in (0, int(T1 / 2)):
        shots.append((f, g))
    if not sheet:
        pipe.stdin.write(g.tobytes())
    i += 1
if sheet:
    f, g = shots[1]
    d = np.clip(np.abs(g.astype(int) - f.astype(int)).sum(2) * 3, 0, 255).astype(np.uint8)
    cv2.imwrite(dst, np.vstack([cv2.resize(g, (1280, int(1280 * H / W))), cv2.resize(cv2.cvtColor(d, cv2.COLOR_GRAY2BGR), (1280, int(1280 * H / W)))]),
                [cv2.IMWRITE_JPEG_QUALITY, 82])
    print('sheet', dst)
else:
    pipe.stdin.close()
    pipe.wait()
    print('wrote', dst, i, 'frames')
