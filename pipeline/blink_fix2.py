"""Deepen the loop's half blinks into full blinks with a sliding lid, keeping their exact timing.

Per eye, a closed-eye still (AI repaint of frame 447, aligned) is Poisson-cloned into each frame so its
edges take that frame's light. The lid is drawn as a solid layer whose lash line travels from the open
upper lid U(x) down to the closed lash line Dc(x); the closed lid above it unfolds from the crease
(rows [Ytop, Dc] of the still squeezed into [Ytop, lash line]). Below the lash line the video's own
iris stays visible, so nothing is ever see-through. How far each frame closes comes from the video's
own lid motion, rescaled so its deepest frame is fully shut.

usage: python3 blink_fix2.py IN.mp4 OUT.mp4|SHEET.jpg wide|tall [sheet]
"""
import sys, subprocess
import cv2
import numpy as np

src, dst, kind = sys.argv[1], sys.argv[2], sys.argv[3]
sheet = len(sys.argv) > 4 and sys.argv[4] == 'sheet'
B = 'blink/'
REF = 447
SHEET_FRAMES = list(range(152, 182, 3)) + list(range(436, 468, 2))

# ---- closure curve per frame (from the tall master's measured iris visibility) ----
Rv = np.load('eye_open_R.npy')


def curve(a, b):
    ref = np.median(Rv[a - 15:a])
    r = Rv[a:b] / ref
    c = (1 - r) / (1 - r.min())
    c = np.convolve(np.pad(c, 1, mode='edge'), [0.25, 0.5, 0.25], mode='valid')
    c = np.clip((c - 0.06) / 0.94, 0, 1)
    return {a + i: float(v) for i, v in enumerate(c)}


CL = {}
DEPTH = {}
for a, b in [(150, 182), (432, 470)]:
    CL.update(curve(a, b))
    ref = np.median(Rv[a - 15:a])
    for i in range(a, b):
        DEPTH[i] = float(1 - (Rv[a:b] / ref).min())   # fraction of the opening the video's lid covers at its deepest

# ---- geometry in wide (2560x1440) coords, frame-447 registration ----
curves = np.load(B + 'curves.npy', allow_pickle=True).item()


def robust_arc(x, u):
    """Smooth upper-lid arc: quartic fit that ignores upward spikes from lash highlights."""
    keep = np.ones_like(u, bool)
    for _ in range(6):
        p = np.polyfit(x[keep], u[keep], 4)
        fit = np.polyval(p, x)
        keep = u >= fit - 10
    return np.polyval(p, x)


import os
CLOSED = B + 'closed_final_nofish.png' if os.path.exists(B + 'closed_final_nofish.png') else B + 'closed_sd5_aligned.png'
closed = cv2.imread(CLOSED)
f432 = cv2.imread(B + 'wide_432.png')
f447 = cv2.imread(B + 'wide_447.png')


def reg_region_w(f):
    return cv2.cvtColor(f[150:900, 800:1650], cv2.COLOR_BGR2GRAY).astype(np.float32)


(d432x, d432y), _ = cv2.phaseCorrelate(reg_region_w(f447), reg_region_w(f432))
EYES = []
for name in ('L', 'R'):
    cv = curves[name]
    x = cv['x'].astype(np.float64)
    U = robust_arc(x, cv['U'])
    D = cv['D']
    Dc = np.maximum(cv['Dc'], U + 40)
    Ytop = U - 90
    EYES.append(dict(x=x - d432x, U=U - d432y, D=D - d432y, Dc=Dc, Ytop=Ytop - d432y))

# paint out the repaint's extra glow / light streak inside the lid zone of the still
hsv = cv2.cvtColor(closed, cv2.COLOR_BGR2HSV)
glow = np.zeros(closed.shape[:2], np.uint8)
for e in EYES:
    for xi, (yt, dc) in zip(e['x'].astype(int), zip(e['Ytop'], e['Dc'])):
        col = slice(int(yt), int(dc) - 25)
        g = (hsv[col, xi, 2] > 205) & (hsv[col, xi, 1] < 75)
        glow[col, xi][g] = 255
glow = cv2.dilate(cv2.morphologyEx(glow, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)), np.ones((21, 21), np.uint8))
if CLOSED.endswith('closed_sd5_aligned.png'):
    closed = cv2.inpaint(closed, glow, 18, cv2.INPAINT_TELEA)
cv2.imwrite(B + 'closed_clean.png', closed)

# ---- map to the output frame size ----
if kind == 'wide':
    sx = sy = 1.0
    oy = 0.0
    size = (2560, 1440)
else:
    sx, sy, oy = 1078 / 2560, 606 / 1440, 539.0
    size = (1078, 1920)
A2 = np.float32([[sx, 0, 0], [0, sy, oy]])
closed = cv2.warpAffine(closed, A2, size, flags=cv2.INTER_AREA)
for e in EYES:
    xs_new = np.arange(int(np.ceil(e['x'].min() * sx)), int(e['x'].max() * sx) + 1)
    for k in ('U', 'D', 'Dc', 'Ytop'):
        e[k] = np.interp(xs_new, e['x'] * sx, e[k] * sy + oy)
    e['x'] = xs_new
s = sx
bubble_w = np.array([1712.0, 512.0])
bubble = np.array([bubble_w[0] * sx, bubble_w[1] * sy + oy])


def reg_region(f):
    x0, x1 = int(800 * sx), int(1650 * sx)
    y0, y1 = int(150 * sy + oy), int(900 * sy + oy)
    return cv2.cvtColor(f[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype(np.float32)


def sm(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def render(f, idx, ref_g, tpl):
    c = CL.get(idx, 0.0)
    if c <= 0.001:
        return f, c
    (dx, dy), _ = cv2.phaseCorrelate(ref_g, reg_region(f))
    Hh, Ww = f.shape[:2]
    cl = cv2.warpAffine(closed, np.float32([[1, 0, dx], [0, 1, dy]]), (Ww, Hh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    hsv_f = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
    keep_video = (((hsv_f[..., 0] < 25) | (hsv_f[..., 0] > 160)) & (hsv_f[..., 1] > 115) & (hsv_f[..., 2] > 60)).astype(np.uint8)
    keep_video = cv2.morphologyEx(keep_video, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    # only koi-sized shapes count; thin red lid lines must not punch holes in the lid
    n, lab, st, _ = cv2.connectedComponentsWithStats(keep_video)
    big = [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] > 6000 * s * s]
    keep_video = np.isin(lab, big).astype(np.uint8)
    keep_video = cv2.dilate(keep_video, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(35 * s) | 1, int(35 * s) | 1)))
    if tpl is not None and 425 <= idx <= 475:
        r = int(150 * s)
        bx, by = bubble + [dx, dy]
        x0, y0 = int(max(bx - r, 0)), int(max(by - r, 0))
        win = f[y0:int(by + r), x0:int(bx + r)]
        if win.shape[0] > tpl.shape[0] and win.shape[1] > tpl.shape[1]:
            res = cv2.matchTemplate(win, tpl, cv2.TM_CCOEFF_NORMED)
            _, score, _, loc = cv2.minMaxLoc(res)
            if score > 0.7:
                cv2.circle(keep_video, (x0 + loc[0] + tpl.shape[1] // 2, y0 + loc[1] + tpl.shape[0] // 2), int(72 * s), 1, -1)
    keep_video = np.clip(cv2.GaussianBlur(keep_video.astype(np.float32), (0, 0), 6 * s + 1) * 1.6, 0, 1)
    out = f.astype(np.float32)
    a_lid = sm(c / 0.25)
    w_low = sm((c - 0.75) / 0.25)
    for e in EYES:
        xs = e['x'] + int(round(dx))
        ok = (xs >= 0) & (xs < Ww)
        xs = xs[ok]
        U, Dc, D, Yt = (e[k][ok] + dy for k in ('U', 'Dc', 'D', 'Ytop'))
        Lt = U + c * (Dc - U)
        tip = 30 * s
        y0 = int(max(Yt.min() - 24 * s, 0))
        y1 = int(min(max(D.max(), Dc.max()) + 50 * s, Hh))
        x0, x1 = int(xs.min()), int(xs.max()) + 1
        # Poisson-clone the closed eye into this frame over the lid box
        mk = np.zeros((Hh, Ww), np.uint8)
        poly_top = np.stack([xs, Yt - 10 * s], 1)
        poly_bot = np.stack([xs[::-1], (np.maximum(D, Dc) + 45 * s)[::-1]], 1)
        cv2.fillPoly(mk, [np.concatenate([poly_top, poly_bot]).astype(np.int32)], 255)
        P = 16
        # koi in front of the eye must not tint the clone's edges: give the clone the still's own pixels there
        dst_c = np.where(keep_video[..., None] > 0.05, cl, f)
        pc = cv2.seamlessClone(cv2.copyMakeBorder(cl, P, P, P, P, cv2.BORDER_REFLECT),
                               cv2.copyMakeBorder(dst_c, P, P, P, P, cv2.BORDER_REFLECT),
                               cv2.copyMakeBorder(cv2.erode(mk, np.ones((3, 3), np.uint8)), P, P, P, P, cv2.BORDER_CONSTANT, value=0),
                               (int((x0 + x1) / 2) + P, int((y0 + y1) / 2) + P), cv2.NORMAL_CLONE)[P:-P, P:-P].astype(np.float32)
        # sliding lid: rows [Yt, Lt] show still rows [Yt, Dc] unfolded; lash tips continue below Lt
        gy = np.arange(y0, y1, dtype=np.float32)[:, None]
        Ytc, Ltc, Dcc = Yt[None, :], Lt[None, :], Dc[None, :]
        k = (Dcc - Ytc) / np.maximum(Ltc - Ytc, 1)
        srcy = np.where(gy <= Ltc, Ytc + (gy - Ytc) * k, gy - Ltc + Dcc).astype(np.float32)
        srcx = np.broadcast_to(xs[None, :].astype(np.float32), srcy.shape).copy()
        lid = cv2.remap(pc, srcx, srcy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        a_top = sm((gy - (Ytc - 20 * s)) / (20 * s))
        a_bot = 1 - sm((gy - Ltc) / tip)
        edge = np.minimum(xs - xs.min(), xs.max() - xs) / (40 * s)
        a_x = sm(edge)[None, :]
        kv = keep_video[y0:y1, x0:x1][:, xs - x0]
        A = (a_lid * a_top * a_bot * a_x * (1 - kv))[..., None]
        # just shut: below the lash line becomes the still's lower lid, so no iris sliver shows
        env = (sm((gy - Ytc) / (10 * s)) * (1 - sm((gy - (np.maximum(D, Dc)[None, :] + 30 * s)) / (15 * s))) * a_x * (1 - kv))[..., None]
        base = out[y0:y1][:, xs] * (1 - w_low * env) + pc[y0:y1][:, xs] * (w_low * env)
        comp = base * (1 - A) + lid * A
        # underwater light stays on the face: put the video's own bright patches back over the lid,
        # only above where the video's own lid edge is, so the white of the eye never shows through
        fv = f[y0:y1][:, xs].astype(np.float32)
        hv = hsv_f[y0:y1][:, xs].astype(np.float32)
        Ut = U[None, :] + c * DEPTH.get(idx, 0.4) * (Dc - U)[None, :]
        light = sm((hv[..., 2] - 180) / 40) * (hv[..., 1] < 95) * (gy < Ut - 12 * s)
        light = cv2.GaussianBlur(light.astype(np.float32), (0, 0), 4 * s + 1)[..., None] * A
        comp = comp * (1 - light) + np.maximum(comp, fv) * light
        out[y0:y1, xs] = comp
    return np.clip(out, 0, 255).astype(np.uint8), c


cap = cv2.VideoCapture(src)
fps = cap.get(cv2.CAP_PROP_FPS) or 30
W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
assert (W, H) == size, (W, H, size)
cap2 = cv2.VideoCapture(src)
cap2.set(cv2.CAP_PROP_POS_FRAMES, REF)
_, reff = cap2.read()
ref_g = reg_region(reff)
r = int(55 * s)
tpl = reff[int(bubble[1] - r):int(bubble[1] + r), int(bubble[0] - r):int(bubble[0] + r)].copy()
if not sheet:
    p = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', f'{fps}',
                         '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', '12', '-pix_fmt', 'yuv420p', '-an', dst], stdin=subprocess.PIPE)
shots = []
idx = 0
while True:
    ok, f = cap.read()
    if not ok:
        break
    g, c = render(f, idx, ref_g, tpl) if idx in CL else (f, 0.0)
    if sheet and idx in SHEET_FRAMES:
        shots.append((idx, c, f, g))
    if not sheet:
        p.stdin.write(g.tobytes())
    idx += 1
if not sheet:
    p.stdin.close()
    p.wait()
    print(f'wrote {dst}: {idx} frames')
else:
    y0, y1 = (int(200 * sy + oy), int(820 * sy + oy))
    tiles = []
    for i, c, f, g in shots:
        t = np.hstack([f[y0:y1], g[y0:y1]])
        t = cv2.resize(t, (1600, int(1600 * t.shape[0] / t.shape[1])), interpolation=cv2.INTER_AREA)
        cv2.putText(t, f'{i}  c={c:.2f}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        tiles.append(t)
    im = np.vstack(tiles)
    h = im.shape[0]
    n = 3
    for j in range(n):
        cv2.imwrite(dst.replace('.jpg', f'_{j}.jpg'), im[j * h // n:(j + 1) * h // n], [cv2.IMWRITE_JPEG_QUALITY, 80])
    print('sheet', dst, len(tiles))
