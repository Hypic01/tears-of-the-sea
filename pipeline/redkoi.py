"""Make the red koi that swims in near the loop point solid instead of a see-through ghost.

The side-extension AI drew this koi's body faint. A solid body was painted once (AI retouch on frame 0);
that koi is cut out and moved along the head's tracked straight path. It stays behind her dark hair and
behind the big orange koi (they occlude it), so it slides out from behind them rather than appearing.
Our own portrait keeps its head; the sprite only covers the side area. It hands back to the AI's own
(by then solid) koi a little after the loop point.

usage: python3 redkoi.py IN.mp4 OUT.mp4 [probe|sheet]
"""
import sys, subprocess
import cv2
import numpy as np

src, dst = sys.argv[1], sys.argv[2]
mode = sys.argv[3] if len(sys.argv) > 3 else ''
R = 'redkoi/'
PXR = 873 + 809                         # right edge of our portrait band
base = cv2.imread(R + 'f0.png')
edit = cv2.imread(R + 'sd_al.png')

# ---- cut the koi (head + painted body + tail) out of the edited frame ----
union = cv2.imread(R + 'mask0.png', 0)
tail = np.array([(2105, 965), (2140, 850), (2270, 840), (2340, 1000), (2260, 1095), (2160, 1095)], np.int32)
head = np.array([(1470, 1180), (1660, 1130), (1690, 1350), (1480, 1350)], np.int32)
cv2.fillPoly(union, [tail, head], 255)
x0, y0, x1, y1 = 1400, 800, 2400, 1440
crop = edit[y0:y1, x0:x1].copy()
u = union[y0:y1, x0:x1]
gc = np.where(cv2.dilate(u, np.ones((41, 41), np.uint8)) > 0, cv2.GC_PR_BGD, cv2.GC_BGD).astype(np.uint8)
gc[u > 0] = cv2.GC_PR_FGD
gc[cv2.erode(u, np.ones((61, 61), np.uint8)) > 0] = cv2.GC_FGD
bg, fg = np.zeros((1, 65)), np.zeros((1, 65))
cv2.grabCut(crop, gc, None, bg, fg, 6, cv2.GC_INIT_WITH_MASK)
a = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8)
nl, lab, st, _ = cv2.connectedComponentsWithStats(a)
big = 1 + int(np.argmax(st[1:, 4]))
a = (lab == big).astype(np.float32)
a = cv2.GaussianBlur(cv2.erode(a, np.ones((3, 3), np.uint8)), (0, 0), 1.5)
SPR = np.zeros(base.shape, np.float32); SPR[y0:y1, x0:x1] = crop
SA = np.zeros(base.shape[:2], np.float32); SA[y0:y1, x0:x1] = a
cv2.imwrite(R + 'sprite_preview.jpg', cv2.resize((SPR * SA[..., None])[y0:y1, x0:x1].astype(np.uint8), (500, 320)), [cv2.IMWRITE_JPEG_QUALITY, 85])

# ---- motion: straight line fitted to the tracked head (virtual time: frames before the loop point are negative)
trk = np.load(R + 'track.npy', allow_pickle=True).item()
pts = [(t if t <= 100 else t - 533, p) for t, p in trk.items() if (t >= 508 or t <= 40)]
T = np.array([p[0] for p in pts], float); P = np.array([p[1] for p in pts], float)
vx = np.polyfit(T, P[:, 0], 1); vy = np.polyfit(T, P[:, 1], 1)
v = np.array([vx[0], vy[0]]); p0 = np.array([np.polyval(vx, 0), np.polyval(vy, 0)])
print('head velocity px/frame', np.round(v, 2), 'head at loop point', np.round(p0, 1))
TS, TE0, TE1 = -150, 30, 52                 # window start, hand-back start/end (virtual frames)

xx = np.arange(base.shape[1], dtype=np.float32)
seam_w = np.clip((xx - (PXR - 95)) / 55, 0, 1)[None, :]          # our portrait keeps its head


def occluders(f):
    h = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
    hair = ((h[..., 2] < 88) & ~((h[..., 0] < 22) | (h[..., 0] > 168))).astype(np.uint8)
    hair = cv2.morphologyEx(hair, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    orange = (((h[..., 0] >= 8) & (h[..., 0] < 24)) & (h[..., 1] > 150) & (h[..., 2] > 150)).astype(np.uint8)   # the bright orange koi
    orange = cv2.dilate(cv2.morphologyEx(orange, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8)), np.ones((9, 9), np.uint8))
    return cv2.GaussianBlur(np.maximum(hair, orange).astype(np.float32), (0, 0), 2.0)


def layer(f, tau):
    off = v * tau
    M = np.float32([[1, 0, off[0]], [0, 1, off[1]]])
    img = cv2.warpAffine(SPR, M, (f.shape[1], f.shape[0]), flags=cv2.INTER_LINEAR)
    al = cv2.warpAffine(SA, M, (f.shape[1], f.shape[0]), flags=cv2.INTER_LINEAR)
    occ = occluders(f) if tau < TE0 else occluders(f) * float(np.clip((TE1 - tau) / (TE1 - TE0), 0, 1))
    wt = 1.0 if tau < TE0 else float(np.clip((TE1 - tau) / (TE1 - TE0), 0, 1)) ** 1.0
    A = al * seam_w * (1 - occ) * wt
    return img, A


cap = cv2.VideoCapture(src)
fps = cap.get(cv2.CAP_PROP_FPS) or 30
W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)); N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
if mode == '':
    pipe = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', f'{fps}',
                             '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-pix_fmt', 'yuv420p', '-an', dst], stdin=subprocess.PIPE)
shots = []
i = 0
while True:
    ok, f = cap.read()
    if not ok:
        break
    tau = i if i <= 100 else i - N
    g = f
    if TS <= tau <= TE1:
        img, A = layer(f, tau)
        if mode == 'probe' and tau % 10 == 0:
            print(tau, 'visible koi px %d' % int(A.sum()))
        g = np.clip(f * (1 - A[..., None]) + img * A[..., None], 0, 255).astype(np.uint8)
        if mode == 'sheet' and tau in (-140, -110, -80, -60, -45, -30, -15, 0, 15, 30, 40, 50):
            s_ = cv2.resize(g[640:1440, 1300:2560], (504, 320)); cv2.putText(s_, str(i), (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2); shots.append(s_)
    if mode == '':
        pipe.stdin.write(g.tobytes())
    i += 1
if mode == 'sheet':
    cv2.imwrite(dst, np.vstack([np.hstack(shots[k:k + 4]) for k in range(0, 12, 4)]), [cv2.IMWRITE_JPEG_QUALITY, 82])
    print('sheet', dst)
elif mode == '':
    pipe.stdin.close(); pipe.wait()
    print('wrote', dst, i, 'frames')
