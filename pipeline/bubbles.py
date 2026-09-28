"""Loop-exact rising bubbles for the underwater hero.

Each bubble rises a whole number of times per loop and wobbles with a whole number of periods, so the
last frame flows into the first. Drawn in the painting's bubble style: a slight lens (magnified water
behind it), a thin bright rim, a crescent highlight and a small glint. Kept to the open water on the
sides and the edges, away from her eyes and mouth.

usage: python3 bubbles.py IN.mp4 OUT.mp4 wide|tall [sheet]
"""
import sys, subprocess
import cv2
import numpy as np

src, dst, kind = sys.argv[1], sys.argv[2], sys.argv[3]
sheet = 'sheet' in sys.argv[4:]
cap = cv2.VideoCapture(src)
fps = cap.get(cv2.CAP_PROP_FPS) or 30
W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
rng = np.random.default_rng(7)
u = H / 1440.0 if kind == 'wide' else H / 1920.0 * 1.33           # px per desktop-reference px

if kind == 'wide':
    lanes = [(40, 760)] * 7 + [(1800, 2520)] * 7 + [(760, 900), (1660, 1800)]
    count = 16
else:
    lanes = [(20, 200)] * 4 + [(880, 1058)] * 4
    count = 8

B = []
for k in range(count):
    lo, hi = lanes[k % len(lanes)]
    base_r = float(rng.choice([6, 8, 10, 13, 17, 23], p=[.2, .22, .2, .16, .13, .09]))
    trail = 1 if base_r > 12 else int(rng.integers(1, 4))            # small ones often rise in short strings
    x0 = float(rng.uniform(lo, hi))
    m = int(rng.choice([1, 2], p=[.6, .4]))                          # rises per loop
    ph = float(rng.uniform(0, 1))
    q = int(rng.integers(5, 10)); psi = float(rng.uniform(0, 2 * np.pi))
    for j in range(trail):
        r = base_r * (1 - 0.18 * j) * u
        B.append(dict(x0=x0 + rng.uniform(-6, 6) * u, r=r, m=m, ph=(ph + j * 0.022) % 1, q=q, psi=psi + j * 0.6,
                      amp=(0.6 + base_r * 0.25) * u, op=float(rng.uniform(0.75, 1.0))))
print(f'{len(B)} bubbles')

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)


def draw(f, i):
    out = f.astype(np.float32)
    for b in B:
        r = b['r']
        L = H + 6 * r
        cy = H + 3 * r - ((b['ph'] + b['m'] * i / N) % 1.0) * L
        cx = b['x0'] + b['amp'] * np.sin(2 * np.pi * b['q'] * i / N + b['psi'])
        if cy < -3 * r or cy > H + 3 * r:
            continue
        x0, x1 = int(max(cx - 2 * r - 2, 0)), int(min(cx + 2 * r + 3, W))
        y0, y1 = int(max(cy - 2 * r - 2, 0)), int(min(cy + 2 * r + 3, H))
        if x1 <= x0 or y1 <= y0:
            continue
        X = xx[y0:y1, x0:x1] - cx; Y = yy[y0:y1, x0:x1] - cy
        d = np.sqrt(X * X + Y * Y)
        inside = np.clip(r - d + 0.8, 0, 1.6) / 1.6
        # lens: water behind the bubble, slightly magnified
        mapx = np.ascontiguousarray(cx + X * 0.82 - x0, np.float32)
        mapy = np.ascontiguousarray(cy + Y * 0.82 - y0, np.float32)
        lens = cv2.remap(f[y0:y1, x0:x1].copy(), mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT).astype(np.float32)
        patch = out[y0:y1, x0:x1]
        patch = patch * (1 - inside[..., None] * 0.9) + (lens * 1.06 + 10) * (inside[..., None] * 0.9)
        # thin bright rim, a little stronger on the lower-right like the painted bubbles
        rim_w = 0.10 * r + 0.7
        rim = np.exp(-((d - r) / rim_w) ** 2) * (0.62 + 0.3 * np.clip((X + Y) / (1.4 * r), 0, 1))
        # crescent highlight upper-left and a small glint lower-right
        hx, hy = X + 0.38 * r, Y + 0.38 * r
        hl = np.clip(1 - (hx * hx / (0.30 * r) ** 2 + hy * hy / (0.20 * r) ** 2), 0, 1) ** 0.6 * 0.9
        gx, gy = X - 0.42 * r, Y - 0.45 * r
        gl = np.clip(1 - (gx * gx + gy * gy) / (0.11 * r + 0.6) ** 2, 0, 1) * 0.55
        a = np.clip(rim + hl + gl, 0, 1)[..., None] * b['op']
        white = np.array([255, 250, 238], np.float32)
        patch = patch * (1 - a) + white * a
        out[y0:y1, x0:x1] = patch
    return np.clip(out, 0, 255).astype(np.uint8)


if not sheet:
    pipe = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', f'{fps}',
                             '-i', '-', '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p', '-c:v', 'libx264', '-preset', 'slow', '-crf', '14',
                             '-x264-params', 'colorprim=bt709:transfer=bt709:colormatrix=bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
                             '-colorspace', 'bt709', '-color_range', 'tv', '-an', dst], stdin=subprocess.PIPE)
shots = []
i = 0
# decode with the right colour matrix (OpenCV's own decode shifts BT.709 video slightly toward green)
dec = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-i', src, '-vf', 'scale=in_color_matrix=bt709:in_range=tv:out_range=pc,format=bgr24',
                        '-f', 'rawvideo', '-'], stdout=subprocess.PIPE)
while True:
    buf = dec.stdout.read(W * H * 3)
    if len(buf) < W * H * 3:
        break
    f = np.frombuffer(buf, np.uint8).reshape(H, W, 3).copy()
    g = draw(f, i)
    if sheet and i in (0, 150):
        shots.append(g)
    if not sheet:
        pipe.stdin.write(g.tobytes())
    i += 1
if sheet:
    cv2.imwrite(dst, np.hstack([cv2.resize(s, (W // 2, H // 2), interpolation=cv2.INTER_AREA) for s in shots]), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print('sheet', dst)
else:
    pipe.stdin.close(); pipe.wait()
    print('wrote', dst, i, 'frames')
