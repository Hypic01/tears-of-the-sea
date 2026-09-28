"""Build the hero loop in layers: a koi-free background with each koi laid on top as its own piece.

Why: in the one-piece AI video the model lost track of overlapping fish (merges, dissolves, cut fish).
Here every koi is its own green-screen clip (one fish per clip, swimming in place) moved along a straight
path over a background that has no fish in it. A fish cannot merge, dissolve or be cut, because nothing
is generated at composite time.

Loop maths: the loop is N frames. Each swim clip is a 150-frame loop and N is a multiple of 150. Each koi
travels exactly one path length per loop and jumps back to the start only while it is fully outside the
frame. Side drift and tilt use whole numbers of periods. So frame N-1 flows into frame 0.

Blending (so the fish do not look pasted on): each koi has a depth from 0 (front) to 1 (back). Deeper fish are
hazier and softer (they stay solid and in front of her hair). Every fish is lit by the scene under it, shadows fall only on skin and
hair (never on open water), edges pick up the water colour, and one grain layer covers everything.

Timing: `plan` searches for start offsets where no two fish overlap head to head and two to four fish are
on screen at every moment, then writes them back into the config.

usage: python3 layered_build.py CONFIG.json OUT.mp4 [sheet|stills|plan]
"""
import json, sys, subprocess
import cv2
import numpy as np

cfg = json.load(open(sys.argv[1]))
out_path = sys.argv[2]
sheet = 'sheet' in sys.argv[3:]
stills = 'stills' in sys.argv[3:]
plan = 'plan' in sys.argv[3:]
W, H = 2560, 1440
N = cfg['frames']


def read(path):
    cap = cv2.VideoCapture(path); F = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        F.append(f)
    return F


def key(f):
    """green screen -> (despilled colour, alpha)"""
    f = f.astype(np.float32)
    b, g, r = f[..., 0], f[..., 1], f[..., 2]
    a = 1 - np.clip((g - np.maximum(r, b) - 22) / 60, 0, 1)
    a = cv2.erode(a, np.ones((3, 3), np.uint8))
    a = cv2.GaussianBlur(a, (0, 0), 1.1)
    g2 = np.minimum(g, np.maximum(r, b) + 4)
    return np.dstack([b, g2, r]), a


# ---- background: clips joined end to end (each starts and ends on the same still), graded to the cover
plate = []
for p in cfg['plates']:
    plate += read(p)
assert len(plate) == N, (len(plate), N)
lut = None
if cfg.get('plate_lut'):
    lut = np.load(cfg['plate_lut'])          # polynomial colour fit, see fit below


def feats(x):
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    return np.stack([np.ones_like(r), r, g, b, r * r, g * g, b * b, r * g, r * b, g * b], -1)


def grade(f):
    if lut is None:
        return f
    x = f[..., ::-1].astype(np.float32) / 255
    y = np.clip(feats(x) @ lut, 0, 1)
    return (y[..., ::-1] * 255).astype(np.float32)


# ---- koi
frame_box = np.array([[0, 0], [W, 0], [W, H], [0, H]], np.float32)
kois = []
for k in cfg['koi']:
    raw = read(k['clip'])
    if k.get('flip'):
        raw = [cv2.flip(f, 1) for f in raw]
    a0 = key(raw[0])[1]
    ys, xs = np.where(a0 > 0.5)
    pts = np.stack([xs, ys], 1).astype(np.float32)
    c = pts.mean(0)
    _, _, vt = np.linalg.svd(pts - c, full_matrices=False)
    ax = vt[0]
    hint = np.array(k['heading_hint'], np.float32) * (np.array([-1, 1]) if k.get('flip') else 1)
    if np.dot(ax, hint) < 0:
        ax = -ax
    proj = (pts - c) @ ax
    length = proj.max() - proj.min()
    sc = k['length'] / length
    # crop the sprite to the fish (plus room for the tail sweep) so warps stay cheap
    pad = 140
    x0, x1 = max(int(xs.min()) - pad, 0), min(int(xs.max()) + pad, a0.shape[1])
    y0, y1 = max(int(ys.min()) - pad, 0), min(int(ys.max()) + pad, a0.shape[0])
    # keyed per frame on the crop only and kept as 8-bit, or seven clips do not fit in memory
    spr = []
    for f in raw:
        rgb, a = key(f[y0:y1, x0:x1])
        spr.append((np.clip(rgb, 0, 255).astype(np.uint8), (a * 255).astype(np.uint8)))
    del raw
    centre = c - np.array([x0, y0])
    painted = ax / np.linalg.norm(ax)          # the way the fish points in its clip
    heading = np.array(k['dir'], np.float32); heading /= np.linalg.norm(heading)   # the way it travels
    turn = -np.degrees(np.arctan2(heading[1], heading[0]) - np.arctan2(painted[1], painted[0]))
    turn = (turn + 180) % 360 - 180
    p0 = np.array(k['pos'], np.float32)       # a point the path passes through
    # how far along the line the fish is visible: project the frame corners, add the fish's own reach
    reach = k['length'] * 0.75 + 160
    s = (frame_box - p0) @ heading
    # the line leaves the frame where it crosses an edge; find entry/exit of the centre line, then add reach
    ts = []
    for t in np.linspace(-6000, 6000, 12001):
        q = p0 + heading * t
        if 0 <= q[0] <= W and 0 <= q[1] <= H:
            ts.append(t)
    s_in, s_out = min(ts) - reach, max(ts) + reach
    D = (s_out - s_in) + k.get('gap', 400)
    kois.append(dict(name=k['name'], spr=spr, centre=centre, sc=sc, heading=heading, p0=p0, s_in=s_in - k.get('gap', 400) / 2, D=D, turn=turn, at0=k.get('at0', 0.0),
                     depth=k.get('depth', 0.0), phase=k.get('phase', 0), drift=k.get('drift', 18), drift_n=k.get('drift_n', 2), tilt=k.get('tilt', 2.0), order=k.get('order', 0)))
    print(f"{k['name']}: scale {sc:.2f}, turn {turn:.0f} deg, heading {np.round(heading, 2)}, path {D:.0f}px, speed {D / N:.2f}px/frame, visible {(s_out - s_in) / (D / N) / 30:.1f}s of {N / 30:.0f}s")
kois.sort(key=lambda k: k['order'])


def place(k, i):
    s = k['s_in'] + (k['at0'] * k['D'] + k['D'] * i / N) % k['D']
    side = np.array([-k['heading'][1], k['heading'][0]])
    w = 2 * np.pi * k['drift_n'] * i / N
    pos = k['p0'] + k['heading'] * s + side * k['drift'] * np.sin(w)
    ang = k['turn'] + k['tilt'] * np.cos(w)
    n = len(k['spr'])
    rgb, a = k['spr'][(int(round(i * 4 * n / N)) + k['phase']) % n]     # four swim cycles per loop, whatever N is
    rgb = rgb.astype(np.float32); a = a.astype(np.float32) / 255
    M = cv2.getRotationMatrix2D((float(k['centre'][0]), float(k['centre'][1])), ang, k['sc'])
    M[:, 2] += pos - k['centre']
    rgbw = cv2.warpAffine(rgb, M, (W, H), flags=cv2.INTER_LINEAR)
    aw = cv2.warpAffine(a, M, (W, H), flags=cv2.INTER_LINEAR)
    return rgbw, aw


if plan:
    U = 100
    M, vis = [], []
    for k in kois:
        rows = []
        for u in range(U):
            keep = k['at0']; k['at0'] = u / U
            _, a = place(k, 0)
            k['at0'] = keep
            rows.append((cv2.resize(a, (160, 90), interpolation=cv2.INTER_AREA) > 0.3).astype(np.float32).ravel())
        M.append(np.array(rows)); vis.append(M[-1].sum(1) > 60)
    O = {(a, b): M[a] @ M[b].T for a in range(len(kois)) for b in range(a + 1, len(kois))}
    fixed = {n: int(round(k['at0'] * U)) for n, k in enumerate(kois) if k['name'] in cfg.get('plan_keep', [])}
    J = np.arange(U)

    def cost(o):
        c = sum(O[a, b][(J + o[a]) % U, (J + o[b]) % U].sum() for a, b in O)
        cnt = sum(vis[n][(J + o[n]) % U].astype(int) for n in range(len(kois)))
        return c + 400 * np.maximum(0, 2 - cnt).sum() + 250 * np.maximum(0, cnt - 4).sum(), c, cnt
    rng = np.random.default_rng(3)
    start = [int(round(k['at0'] * U)) for k in kois]
    best, bo = cost(start)[0], list(start)
    print('current offsets', start, 'overlap', int(cost(start)[1]), 'fish on screen min/max', cost(start)[2].min(), cost(start)[2].max())
    for it in range(40000):
        o = list(bo) if it % 3 else [int(rng.integers(U)) for _ in kois]
        n = int(rng.integers(len(kois)))
        o[n] = int(rng.integers(U)) if it % 3 == 0 else (o[n] + int(rng.integers(-6, 7))) % U
        for f, v in fixed.items():
            o[f] = v
        c = cost(o)[0]
        if c < best:
            best, bo = c, o
    tot, ov, cnt = cost(bo)
    print('best offsets', bo, 'overlap', int(ov), 'fish on screen min/max', cnt.min(), cnt.max())
    for (a, b), m in O.items():
        v = m[(J + bo[a]) % U, (J + bo[b]) % U]
        if v.max() > 0:
            print(f"  {kois[a]['name']}+{kois[b]['name']}: overlap for {int((v > 0).sum())}% of the loop, peak {int(v.max())} px of 14400")
    names = {k['name']: bo[n] / U for n, k in enumerate(kois)}
    for k in cfg['koi']:
        k['at0'] = names[k['name']]
    json.dump(cfg, open(sys.argv[1], 'w'), indent=1)
    sys.exit(0)

if not sheet and not stills:
    pipe = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', '30', '-i', '-',
                             '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p', '-c:v', 'libx264', '-preset', 'slow', '-crf', '14',
                             '-x264-params', 'colorprim=bt709:transfer=bt709:colormatrix=bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
                             '-colorspace', 'bt709', '-color_range', 'tv', '-an', out_path], stdin=subprocess.PIPE)
shots = []
step = cfg.get('sheet_step', 25)
yy, xx = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32) * 4


def caustics(i):
    """moving light ripples shared by the fish and the scene; whole numbers of periods, so it loops"""
    ph = 2 * np.pi * i / N
    v = (np.sin(xx * 0.011 + yy * 0.006 + 3 * ph) + np.sin(xx * -0.007 + yy * 0.013 + 2 * ph + 1.3)
         + np.sin(xx * 0.004 + yy * -0.015 - 4 * ph + 2.1) + np.sin((xx + yy) * 0.009 + 5 * ph + 0.4))
    c = np.exp(-np.abs(v) * 1.35)                   # thin bright lines where the waves cancel
    c = cv2.GaussianBlur(c, (0, 0), 2.5)
    return cv2.resize(c, (W, H), interpolation=cv2.INTER_CUBIC) - 0.32


rng = np.random.default_rng(11)
grain = [rng.normal(0, 1.6, (H // 2, W // 2)).astype(np.float32) for _ in range(12)]
for i in range(N):
    if sheet and i % step:
        continue
    if stills and i not in cfg.get('stills', [0]):
        continue
    bg = grade(cv2.resize(plate[i], (W, H), interpolation=cv2.INTER_LANCZOS4)).astype(np.float32)
    plate_i = bg.copy()
    water = cv2.GaussianBlur(bg, (0, 0), 40)
    hsv = cv2.cvtColor(np.clip(bg, 0, 255).astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
    lum = cv2.GaussianBlur(hsv[..., 2], (0, 0), 28)
    light = np.clip(0.80 + 0.42 * lum / 190.0, 0.78, 1.18)                       # scene light under each fish
    is_water = ((hsv[..., 0] > 85) & (hsv[..., 0] < 112) & (hsv[..., 1] > 95) & (hsv[..., 2] > 125)).astype(np.float32)
    is_water = cv2.GaussianBlur(is_water, (0, 0), 14)
    hair = np.clip((105 - hsv[..., 2]) / 45, 0, 1)                                 # dark hair, soft edge
    hair = cv2.GaussianBlur(hair, (0, 0), 1.6)
    ca = caustics(i)
    bg = bg * (1 + 0.07 * ca[..., None] * (1 - hair[..., None]))
    for k in kois:
        rgb, a = place(k, i)
        if a.max() < 0.01:
            continue
        ys, xs = np.where(a > 0.003)
        y0, y1, x0, x1 = max(ys.min() - 140, 0), min(ys.max() + 140, H), max(xs.min() - 140, 0), min(xs.max() + 140, W)
        a_ = a[y0:y1, x0:x1]; rgb_ = rgb[y0:y1, x0:x1]; b_ = bg[y0:y1, x0:x1]; w_ = water[y0:y1, x0:x1]
        d = k['depth']
        # match the painting: a little softer, less saturated, lit by what is under it, hazier with depth
        col = cv2.GaussianBlur(rgb_, (0, 0), 0.9 + 1.3 * d)
        a_ = cv2.GaussianBlur(a_, (0, 0), 1.2 + 1.2 * d)
        grey = col.mean(2, keepdims=True)
        col = col * (0.86 - 0.10 * d) + grey * (0.14 + 0.10 * d)
        col = col * light[y0:y1, x0:x1, None] * (1 + (0.30 - 0.12 * d) * ca[y0:y1, x0:x1, None])
        col = col * (0.80 + 0.20 * w_ / np.maximum(w_.max(axis=(0, 1), keepdims=True), 1) * 1.15)   # ambient water light
        haze = 0.13 + 0.25 * d
        col = col * (1 - haze) + w_ * haze
        edge = np.clip(a_ - cv2.erode(a_, np.ones((9, 9), np.uint8)), 0, 1)
        edge = cv2.GaussianBlur(edge, (0, 0), 3)[..., None] * 0.45                # water colour wraps the outline
        col = col * (1 - edge) + w_ * edge
        # fish never go behind her hair: hair has bright highlights, so a hair mask leaves fish half see-through
        # contact shadow: only on skin and hair, never on open water
        sh = cv2.warpAffine(a_, np.float32([[1, 0, 14], [0, 1, 22]]), (a_.shape[1], a_.shape[0]))
        sh = cv2.GaussianBlur(sh, (0, 0), 20) * (0.34 - 0.14 * d) * (1 - is_water[y0:y1, x0:x1])
        b_ = b_ * (1 - sh[..., None] * np.array([0.75, 0.9, 1.0], np.float32))   # shadow leans cool, like the water
        bg[y0:y1, x0:x1] = b_ * (1 - a_[..., None]) + col * a_[..., None]
    g = cv2.resize(grain[i % len(grain)], (W, H), interpolation=cv2.INTER_LINEAR)
    out = np.clip(bg + g[..., None], 0, 255).astype(np.uint8)
    if sheet:
        t = cv2.resize(out, (640, 360), interpolation=cv2.INTER_AREA)
        cv2.putText(t, str(i), (6, 22), cv2.FONT_HERSHEY_SIMPLEX, .7, (255, 255, 255), 2); shots.append(t)
    elif stills:
        cv2.imwrite(out_path.replace('.jpg', f'_{i:03d}.jpg'), out, [cv2.IMWRITE_JPEG_QUALITY, 92])
    else:
        pipe.stdin.write(out.tobytes())
if sheet:
    rows = [np.hstack(shots[j:j + 4]) for j in range(0, len(shots) - len(shots) % 4, 4)]
    cv2.imwrite(out_path, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 82]); print('sheet', out_path)
elif stills:
    print('stills written')
else:
    pipe.stdin.close(); pipe.wait(); print('wrote', out_path, N, 'frames')
