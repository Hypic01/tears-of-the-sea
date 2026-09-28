"""Full-face 16:9 hero from two AI re-frames, one set of koi, loop-exact.

Pass A re-framed the loop as is (its own start/end jump sits at our frame 0). Pass B re-framed the
loop rotated to start at frame ROT (its jump sits at our frame ROT). Each side shows B around our
loop point and A around ROT, switching once in each half of the loop at the frames where A and B
agree best, so no koi ever fades or doubles. Our sharp portrait stays in the middle.

usage: python3 widen2.py PORTRAIT.mp4 A.mp4 B.mp4 ROT OUT.mp4 [out_h=1440] [sheet]
"""
import sys, subprocess
import cv2
import numpy as np

src, a_path, b_path, ROT, dst = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
OH = int(sys.argv[6]) if len(sys.argv) > 6 else 1440
sheet = 'sheet' in sys.argv[7:]
OW = int(round(OH * 16 / 9 / 2)) * 2
XF = 12                                   # frames for each A<->B switch


def read_all(path):
    cap = cv2.VideoCapture(path)
    fr = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        fr.append(f)
    return fr, cap.get(cv2.CAP_PROP_FPS) or 30


P, fps = read_all(src)
Braw, _ = read_all(b_path)
A = Braw                                  # placement comes from the narrow pass itself
n = len(P)
assert len(A) == n and len(Braw) == n, (len(A), len(Braw), n)
B = [Braw[(i - ROT) % n] for i in range(n)]            # B re-indexed to our timeline
ah, aw = A[0].shape[:2]


CROP = (150, 928)                         # the AI was given only these portrait columns


def locate(F):
    g0 = cv2.cvtColor(F[0], cv2.COLOR_BGR2GRAY)
    tplf = P[(0 - ROT) % n if False else 0][:, CROP[0]:CROP[1]]
    best = None
    for sc in np.linspace(0.9, 1.1, 21) * (ah / P[0].shape[0]):
        tw, th = int(tplf.shape[1] * sc), int(tplf.shape[0] * sc)
        if th > ah + 2 or tw > aw:
            continue
        tpl = cv2.cvtColor(cv2.resize(tplf, (tw, th), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        my, mx = int(th * 0.1), int(tw * 0.1)
        res = cv2.matchTemplate(g0, tpl[my:th - my, mx:tw - mx], cv2.TM_CCOEFF_NORMED)
        _, sco, _, loc = cv2.minMaxLoc(res)
        if best is None or sco > best[0]:
            best = (sco, sc, loc[0] - mx, loc[1] - my)
    return best


lc = locate(B)
la = (lc[0], lc[1], lc[2] - CROP[0] * lc[1], lc[3])
lb = la
print('narrow crop placement', np.round(lc, 3), '-> full portrait placement', np.round(la, 3))
_, sc, ox, oy = la
k = OH / (P[0].shape[0] * sc)
pw = int(round(P[0].shape[1] * sc * k))
px = int(round(ox * k + (OW - aw * k) / 2))
OV = int(round(CROP[0] * sc * k))
print(f'output {OW}x{OH}: portrait {pw}x{OH} at x={px}; overlap with the AI band {OV}px per side')


def edges_of(F, place):
    g = cv2.cvtColor(F[len(F) // 2], cv2.COLOR_BGR2GRAY).astype(np.float32)
    gx = np.abs(np.diff(cv2.GaussianBlur(g, (1, 9), 0), axis=1)).mean(0)
    out = []
    for e in (place[2], place[2] + int(round(P[0].shape[1] * place[1]))):
        lo, hi = max(e - 12, 1), min(e + 12, aw - 2)
        out.append(lo + int(np.argmax(gx[lo:hi])))
    return out


EB = edges_of(B, (lc[0], lc[1] * (CROP[1] - CROP[0]) / P[0].shape[1], lc[2], lc[3]))
EA = EB
print('paste edges A', EA, 'B', EB)


def heal(f, edges):
    for e in edges:
        a0, a1 = e - 12, e + 13
        seg = f[:, a0:a1]
        soft = cv2.GaussianBlur(seg, (0, 0), sigmaX=2.2, sigmaY=0.1)
        w = np.exp(-((np.arange(a0, a1) - (e + 0.5)) ** 2) / (2 * 3.0 ** 2)).astype(np.float32)[None, :, None]
        f[:, a0:a1] = seg * (1 - w) + soft * w
    return f


def up(f, edges, place):
    f = heal(f.astype(np.float32), edges)
    # align B onto A's placement if they differ slightly
    if place is not la:
        s2 = la[1] / place[1]
        M = np.float32([[s2, 0, la[2] - place[2] * s2], [0, s2, la[3] - place[3] * s2]])
        f = cv2.warpAffine(f, M, (aw, ah), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    big = cv2.resize(f, (int(round(aw * k)), int(round(ah * k))), interpolation=cv2.INTER_LANCZOS4)
    canvas = np.zeros((OH, OW, 3), np.float32)
    x0 = int(round((OW - big.shape[1]) / 2))
    canvas[:, max(x0, 0):max(x0, 0) + min(OW, big.shape[1])] = big[:OH, max(-x0, 0):max(-x0, 0) + min(OW, big.shape[1])]
    return canvas


def koi_mask(f):
    h = cv2.cvtColor(np.clip(f, 0, 255).astype(np.uint8), cv2.COLOR_BGR2HSV)
    m = (((h[..., 0] < 22) | (h[..., 0] > 168)) & (h[..., 1] > 140) & (h[..., 2] > 110)).astype(np.uint8)
    return cv2.dilate(m, np.ones((31, 31), np.uint8)).astype(np.float32)


# ---- sides come from pass B only (continuous across our loop point). Its own jump at ROT is bridged by a
# flow-guided morph of the koi-free backgrounds; koi crossing the jump are carried by cut-out sprites.
MW = (352, 378)                           # morph window around ROT


def ramp(x):
    x = float(np.clip(x, 0, 1))
    return x * x * (3 - 2 * x)


# ---- koi sprites for pass B's jump (right side only) ----
def orange_blobs(f, xmin):
    h = cv2.cvtColor(np.clip(f, 0, 255).astype(np.uint8), cv2.COLOR_BGR2HSV)
    m = (((h[..., 0] < 22) | (h[..., 0] > 168)) & (h[..., 1] > 140) & (h[..., 2] > 110)).astype(np.uint8)
    m[:, :xmin] = 0
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    nb, lab, st, _ = cv2.connectedComponentsWithStats(m)
    return m, [(st[i], i, lab) for i in range(1, nb) if st[i, 4] > 1500]


XR = px + pw + int(OH * 0.06)             # right-side region starts just outside the portrait


def box_of(blobs, pick):
    sel = [b for b in blobs if pick(b[0])]
    if not sel:
        return None
    x0 = min(b[0][0] for b in sel); y0 = min(b[0][1] for b in sel)
    x1 = max(b[0][0] + b[0][2] for b in sel); y1 = max(b[0][1] + b[0][3] for b in sel)
    return np.array([x0, y0, x1, y1], float)


is_top = lambda st: st[1] < OH * 0.08                       # the koi leaving through the top edge
is_pair = lambda st: st[1] + st[3] > OH * 0.55              # the pair arriving low on the right


def cut(frame, box):
    x0, y0, x1, y1 = [int(v) for v in box]
    m = 150
    X0, Y0, X1, Y1 = max(x0 - m, 0), max(y0 - m, 0), min(x1 + m, OW), min(y1 + m, OH)
    crop = np.clip(frame[Y0:Y1, X0:X1], 0, 255).astype(np.uint8)
    om, _ = orange_blobs(frame[Y0:Y1, X0:X1], 0)
    gc = np.full(crop.shape[:2], cv2.GC_PR_BGD, np.uint8)
    gc[cv2.dilate(om, np.ones((41, 41), np.uint8)) > 0] = cv2.GC_PR_FGD
    gc[cv2.erode(om, np.ones((9, 9), np.uint8)) > 0] = cv2.GC_FGD
    bg, fg = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(crop, gc, None, bg, fg, 6, cv2.GC_INIT_WITH_MASK)
    a = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8)
    # keep only matte pieces attached to the koi's body, never loose patches of water
    nb, lab, st, _ = cv2.connectedComponentsWithStats(a)
    core = set(np.unique(lab[om > 0])) - {0}
    a = np.isin(lab, list(core)).astype(np.float32)
    a = cv2.GaussianBlur(cv2.erode(a, np.ones((3, 3), np.uint8)), (0, 0), 1.6)
    # fade to nothing at cut-out borders that are inside the frame, so no straight edges ever show
    hh, ww = a.shape
    fy = np.ones(hh, np.float32); fx = np.ones(ww, np.float32)
    ramp_px = 40
    r = np.clip(np.arange(ramp_px) / ramp_px, 0, 1)
    if Y0 > 0: fy[:ramp_px] = np.minimum(fy[:ramp_px], r)
    if Y1 < OH: fy[-ramp_px:] = np.minimum(fy[-ramp_px:], r[::-1])
    if X0 > 0: fx[:ramp_px] = np.minimum(fx[:ramp_px], r)
    if X1 < OW: fx[-ramp_px:] = np.minimum(fx[-ramp_px:], r[::-1])
    a = a * fy[:, None] * fx[None, :]
    return crop.astype(np.float32), a, (X0, Y0)


UB = {}
def ub_at(t):
    if t not in UB:
        UB[t] = up(B[t], EB, lb)
    return UB[t]


MARG = int(OH * 0.03)


def blobs_side(f):
    _, bl = orange_blobs(f, 0)
    return [st for st, _, _ in bl if st[0] + st[2] < px - MARG or st[0] > px + pw + MARG]


cen = lambda st: np.array([st[0] + st[2] / 2.0, st[1] + st[3] / 2.0])


def track(t0, step, count, st0):
    pos = {t0: st0}
    cur = st0
    for j in range(1, count):
        t = t0 + step * j
        bl = blobs_side(ub_at(t))
        if not bl:
            break
        c = min(bl, key=lambda q: np.linalg.norm(cen(q) - cen(cur)))
        if np.linalg.norm(cen(c) - cen(cur)) > 60:
            break
        pos[t] = c
        cur = c
    return pos


def box(st):
    return np.array([st[0], st[1], st[0] + st[2], st[1] + st[3]], float)


SPR = []
for st in blobs_side(ub_at(ROT - 1)):                         # koi the pass shows just before its jump: let them swim out
    tr = track(ROT - 1, -1, 14, st)
    ks = sorted(tr)
    v = (cen(tr[ks[-1]]) - cen(tr[ks[0]])) / max(ks[-1] - ks[0], 1)
    if np.linalg.norm(v) < 1.5:
        v = np.array([-3.0 if st[0] < px else 3.0, 0.0])
    img, al, org = cut(ub_at(ROT - 1), box(st))
    SPR.append(('exit', img, al, org, (lambda v: lambda t: v * (t - ROT + 1) * (1 + (t - ROT + 1) / 30.0))(v), range(ROT, ROT + 150)))
for st in blobs_side(ub_at(ROT)):                             # koi the pass shows right after its jump: let them swim in
    tr = track(ROT, 1, 14, st)
    ks = sorted(tr)
    v = (cen(tr[ks[-1]]) - cen(tr[ks[0]])) / max(ks[-1] - ks[0], 1)
    if np.linalg.norm(v) < 1.5:
        v = np.array([3.0 if st[0] < px else -3.0, 0.0])
    img, al, org = cut(ub_at(ROT), box(st))
    SPR.append(('enter', img, al, org, (lambda v: lambda t: -v * (ROT - t) * (1 + (ROT - t) / 30.0))(v), range(ROT - 150, ROT)))
for sp in SPR:
    print('sprite', sp[0], 'origin', sp[3], 'size', sp[2].shape)


def draw(side, img, a, org, off):
    h, w = a.shape
    M = np.float32([[1, 0, org[0] + off[0]], [0, 1, org[1] + off[1]]])
    big = cv2.warpAffine(img, M, (OW, OH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    al = cv2.warpAffine(a, M, (OW, OH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)[..., None]
    if al.max() < 0.01:
        return side, False
    return side * (1 - al) + big * al, True


def koi_layers(side, i):
    for name, img, al, org, off, frames in SPR:
        if i in frames:
            side, _ = draw(side, img, al, org, off(i))
    return side


def koi_free(f, other):
    """f with its koi replaced by the other frame's pixels (used for the held frames in the morph)."""
    m, _ = orange_blobs(f, 0)
    m = cv2.GaussianBlur(cv2.dilate(m, np.ones((61, 61), np.uint8)).astype(np.float32), (0, 0), 8)[..., None]
    return f * (1 - m) + other * m


def morph(e, s_, w):
    k2 = 0.35
    ge = cv2.cvtColor(cv2.resize(np.clip(e, 0, 255).astype(np.uint8), None, fx=k2, fy=k2), cv2.COLOR_BGR2GRAY)
    gs = cv2.cvtColor(cv2.resize(np.clip(s_, 0, 255).astype(np.uint8), None, fx=k2, fy=k2), cv2.COLOR_BGR2GRAY)
    F = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM).calc(ge, gs, None)
    F = cv2.resize(cv2.GaussianBlur(F, (0, 0), 5), (OW, OH)) / k2
    gx, gy = np.meshgrid(np.arange(OW, dtype=np.float32), np.arange(OH, dtype=np.float32))
    we = cv2.remap(e, gx - w * F[..., 0], gy - w * F[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    ws = cv2.remap(s_, gx + (1 - w) * F[..., 0], gy + (1 - w) * F[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return we * (1 - w) + ws * w


E_END = S_START = None


def side_at(i):
    global E_END, S_START
    b = UB.pop(i) if i in UB else up(B[i], EB, lb)
    if not (MW[0] <= i <= MW[1]):
        return b
    if E_END is None:
        e_last, s_first = ub_at(ROT - 1), ub_at(ROT)
        E_END, S_START = koi_free(e_last, s_first), koi_free(s_first, e_last)
    w = ramp((i - MW[0]) / (MW[1] - MW[0]))
    if i < ROT:
        e_bg, s_bg = koi_free(b, S_START), S_START
    else:
        e_bg, s_bg = E_END, koi_free(b, E_END)
    bg = morph(e_bg, s_bg, w)
    # koi that belong to the live frame stay solid on top of the morphing background
    m, _ = orange_blobs(b, 0)
    m = cv2.GaussianBlur(cv2.dilate(m, np.ones((25, 25), np.uint8)).astype(np.float32), (0, 0), 4)[..., None]
    return bg * (1 - m) + b * m


feather = max(OV - 10, 40)            # crossfade across the overlap only; the AI's paste line stays hidden under our portrait
xx = np.arange(OW, dtype=np.float32)
dd = np.minimum(xx - px, px + pw - 1 - xx)
alpha = np.clip(dd / feather, 0, 1)
alpha = (alpha * alpha * (3 - 2 * alpha))[None, :, None]
sideL = (xx < px + pw / 2)[None, :, None].astype(np.float32)

if not sheet:
    pipe = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{OW}x{OH}', '-r', f'{fps}',
                             '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-pix_fmt', 'yuv420p', '-an', dst], stdin=subprocess.PIPE)
gains = []
shots = []
for i in range(n):
    side = koi_layers(side_at(i), i)
    por = cv2.resize(P[i], (pw, OH), interpolation=cv2.INTER_AREA).astype(np.float32)
    band = int(pw * 0.12)
    ref = np.concatenate([por[:, :band], por[:, -band:]], 1).reshape(-1, 3)
    got = np.concatenate([side[:, px:px + band], side[:, px + pw - band:px + pw]], 1).reshape(-1, 3)
    g = ref.std(0) / np.maximum(got.std(0), 1)
    b = ref.mean(0) - got.mean(0) * g
    gains.append((g, b))
    gs = np.mean([x[0] for x in gains[-15:]], 0)
    bs = np.mean([x[1] for x in gains[-15:]], 0)
    side = side * gs + bs
    # gentle tone match across each seam: a smooth per-row offset measured over the overlap strip (koi and
    # strands excluded), blurred ~120px vertically so it can never draw streaks, clipped, faded outward
    m = 1 - np.maximum(koi_mask(por), koi_mask(side[:, px:px + pw]))
    corr = np.zeros_like(side)
    fade = OH * 0.2
    for lo, hi, xs_out, sgn in ((0, OV, np.arange(px, dtype=np.float32), -1), (pw - OV, pw, np.arange(px + pw, OW, dtype=np.float32), 1)):
        rawb = (por[:, lo:hi] - side[:, px + lo:px + hi]) * m[:, lo:hi, None]
        wsum = m[:, lo:hi].sum(1)[:, None]
        prof = rawb.sum(1) / np.maximum(wsum, 1)
        wprof = np.clip(wsum / (hi - lo), 0, 1)
        prof = cv2.GaussianBlur((prof * wprof)[:, None, :], (0, 0), sigmaX=0.1, sigmaY=120)[:, 0, :] / np.maximum(cv2.GaussianBlur(wprof[:, None].astype(np.float32), (0, 0), sigmaX=0.1, sigmaY=120), 0.05)
        prof = np.clip(prof, -18, 18)
        dist = (px - xs_out) if sgn < 0 else (xs_out - (px + pw))
        wx = np.clip(1 - dist / fade, 0, 1)
        if sgn < 0:
            corr[:, :px] = prof[:, None, :] * wx[None, :, None]
        else:
            corr[:, px + pw:] = prof[:, None, :] * wx[None, :, None]
        inner = np.clip(1 - (np.arange(lo, hi) - (lo if sgn > 0 else hi - 1)) * (-sgn) / max(hi - lo, 1), 0, 1) if False else None
    corr[:, px:px + OV] = corr[:, px - 1:px] if px > 0 else 0
    corr[:, px + pw - OV:px + pw] = corr[:, px + pw:px + pw + 1]
    side = side + corr
    out = side.copy()
    out[:, px:px + pw] = por
    out = side * (1 - alpha) + out * alpha
    o8 = np.clip(out, 0, 255).astype(np.uint8)
    if sheet:
        shots.append(cv2.resize(o8, (640, 360), interpolation=cv2.INTER_AREA))
    else:
        pipe.stdin.write(o8.tobytes())
if sheet:
    np.save(dst, np.array(shots))
    print('saved small frames', dst)
else:
    pipe.stdin.close()
    pipe.wait()
    print('wrote', dst, n, 'frames')
