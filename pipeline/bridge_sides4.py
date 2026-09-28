"""Replace the side areas over [T0, T1] with a keyframed AI bridge clip, hiding the AI pass's mid-loop koi swap.

The bridge was generated from composite frames T0 and T1 as start/end keyframes, so it meets the composite at
both ends; it is still eased in and out over EDGE frames. Our portrait band (plus its overlap) stays untouched.

usage: python3 bridge_sides3.py COMPOSITE.mp4 BRIDGE.mp4 T0 T1 OUT.mp4 [sheet]   (T1 may exceed the loop length: the window wraps)
"""
import sys, subprocess
import cv2
import numpy as np

src, brg, T0, T1, dst = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
sheet = 'sheet' in sys.argv[6:]

PX, PW = 873, 809                          # portrait band in the 2560x1440 composite
FEATHER = 90
EDGE = 8

cb = cv2.VideoCapture(brg)
BR = []
while True:
    ok, f = cb.read()
    if not ok:
        break
    BR.append(f)
nb = len(BR)
print('bridge frames', nb)

cap = cv2.VideoCapture(src)
fps = cap.get(cv2.CAP_PROP_FPS) or 30
NF = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
xx = np.arange(W, dtype=np.float32)
d = (xx - (PX + PW - 1)) if 'right' in sys.argv[6:] else np.maximum(PX - xx, xx - (PX + PW - 1))   # distance outside the portrait band
wb = np.clip(d / FEATHER, 0, 1)
wb = (wb * wb * (3 - 2 * wb))[None, :, None]


def bridge_at(i):
    t = (i - T0) / (T1 - T0) * (nb - 1)
    j = int(np.floor(t)); a = t - j
    j2 = min(j + 1, nb - 1)
    f = BR[j].astype(np.float32) * (1 - a) + BR[j2].astype(np.float32) * a
    return cv2.resize(f, (W, H), interpolation=cv2.INTER_LANCZOS4)


# colour-match the bridge to the composite on the keyframes (per-channel gain/offset over the side areas)
cap2 = cv2.VideoCapture(src)
cap2.set(cv2.CAP_PROP_POS_FRAMES, T0 % NF); _, c0 = cap2.read()
side_m = (wb[0, :, 0] > 0.5)
ref = c0[:, side_m].reshape(-1, 3).astype(np.float32); got = bridge_at(T0)[:, side_m].reshape(-1, 3)
G = ref.std(0) / np.maximum(got.std(0), 1); O = ref.mean(0) - got.mean(0) * G
print('colour gain', np.round(G, 3), 'offset', np.round(O, 1))

# which bridge koi to draw whole: those touching the side areas, carried forward and backward in time while
# the same koi (overlapping blob) is still visible, so a koi never switches on/off as it crosses her face
side_cols = (wb[0, :, 0] > 0.5)
LAB, KEEP = {}, {}
for i in range(T0, T1 + 1):
    b = bridge_at(i) * G + O
    hb = cv2.cvtColor(np.clip(b, 0, 255).astype(np.uint8), cv2.COLOR_BGR2HSV)
    km = (((hb[..., 0] < 22) | (hb[..., 0] > 168)) & (hb[..., 1] > 130) & (hb[..., 2] > 100)).astype(np.uint8)
    km = cv2.morphologyEx(km, cv2.MORPH_CLOSE, np.ones((21, 21), np.uint8))
    nl, lab, stt, _ = cv2.connectedComponentsWithStats(km)
    LAB[i] = lab
    KEEP[i] = {k for k in range(1, nl) if stt[k, 4] > 3000 and (lab[:, side_cols] == k).any()}
    LAB[i + 0.5] = {k for k in range(1, nl) if stt[k, 4] > 3000}


def propagate(order):
    for a, b in zip(order[:-1], order[1:]):
        prev = np.isin(LAB[a], list(KEEP[a])) if KEEP[a] else np.zeros(LAB[a].shape, bool)
        prev = cv2.dilate(prev.astype(np.uint8), np.ones((25, 25), np.uint8)) > 0
        for k in LAB[b + 0.5]:
            if k not in KEEP[b] and (prev & (LAB[b] == k)).sum() > 800:
                KEEP[b].add(k)


fr = list(range(T0, T1 + 1))
propagate(fr); propagate(fr[::-1]); propagate(fr)
KM = {}
for i in fr:
    km = np.isin(LAB[i], list(KEEP[i])).astype(np.uint8)
    km = cv2.dilate(km, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
    if 'right' in sys.argv[6:]:
        km[:, :PX + PW - 220] = 0                 # never paint bridge koi deep over her face
    KM[i] = cv2.GaussianBlur(km.astype(np.float32), (0, 0), 5)[..., None]
del LAB
print('bridge koi masks ready')

if not sheet:
    pipe = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', f'{fps}',
                             '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-pix_fmt', 'yuv420p', '-an', dst], stdin=subprocess.PIPE)
shots = []
i = 0
while True:
    ok, f = cap.read()
    if not ok:
        break
    v = i if i >= T0 else i + NF                # virtual index, so a window may run across the loop point
    if T0 <= v <= T1:
        i_real = i
        i = v
        e = min(i - T0, T1 - i) / EDGE
        e = float(np.clip(e, 0, 1)); e = e * e * (3 - 2 * e)
        b = bridge_at(i) * G + O
        km = KM[i]
        w = np.maximum(wb, km) * e
        g = np.clip(f.astype(np.float32) * (1 - w) + b * w, 0, 255).astype(np.uint8)
        i = i_real
    else:
        g = f
    if sheet and i in (T0 + 2, 200, 203, 206, 215, 260, T1 - 2):
        shots.append(cv2.resize(g, (640, 360), interpolation=cv2.INTER_AREA))
    if not sheet:
        pipe.stdin.write(g.tobytes())
    i += 1
if sheet:
    cv2.imwrite(dst, np.vstack([np.hstack(shots[:4]), np.hstack(shots[4:] + [np.zeros_like(shots[0])])]), [cv2.IMWRITE_JPEG_QUALITY, 80])
    print('sheet', dst)
else:
    pipe.stdin.close(); pipe.wait()
    print('wrote', dst, i, 'frames')
