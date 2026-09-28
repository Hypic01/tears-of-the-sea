"""Carry the lower-right koi (which the AI fades out) solidly out through the bottom edge.
Sprite cut from frame T0, moved along its own heading with gentle acceleration and a slight tail-sway rotation."""
import sys, subprocess, cv2, numpy as np
src, dst = sys.argv[1], sys.argv[2]; sheet = 'sheet' in sys.argv[3:]
T0 = 400; C0 = np.array([1613., 627.]); V0 = np.array([-3.4, 2.9])
cap = cv2.VideoCapture(src); fps = 30; W, H = 1920, 1080
frames = []
while True:
    ok, f = cap.read()
    if not ok: break
    frames.append(f)
f0 = frames[T0]
h = cv2.cvtColor(f0, cv2.COLOR_BGR2HSV).astype(int)
m = (((h[..., 0] < 24) | (h[..., 0] > 166)) & (h[..., 1] > 110) & (h[..., 2] > 90)).astype(np.uint8)
m[:, :1200] = 0; m[:450] = 0
m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
n, l, st, _ = cv2.connectedComponentsWithStats(m); k = 1 + int(np.argmax(st[1:, 4]))
x, y, w, hh = st[k, :4]; x0, y0, x1, y1 = max(x - 60, 0), max(y - 60, 0), min(x + w + 60, W), min(y + hh + 60, H)
crop = f0[y0:y1, x0:x1].copy(); u = (l[y0:y1, x0:x1] == k).astype(np.uint8)
gc = np.full(u.shape, cv2.GC_PR_BGD, np.uint8); gc[cv2.dilate(u, np.ones((31, 31), np.uint8)) > 0] = cv2.GC_PR_FGD; gc[cv2.erode(u, np.ones((7, 7), np.uint8)) > 0] = cv2.GC_FGD
bg, fg = np.zeros((1, 65)), np.zeros((1, 65)); cv2.grabCut(crop, gc, None, bg, fg, 6, cv2.GC_INIT_WITH_MASK)
a = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8)
n2, l2, s2, _ = cv2.connectedComponentsWithStats(a); a = (l2 == 1 + int(np.argmax(s2[1:, 4]))).astype(np.float32)
a = cv2.GaussianBlur(cv2.erode(a, np.ones((3, 3), np.uint8)), (0, 0), 1.4)
cv2.imwrite('audit/koi_sprite.jpg', (crop * a[..., None]).astype(np.uint8))
pc = C0 - np.array([x0, y0])                      # sprite pivot (koi centre) in crop coords
def pos(t):
    d = t - T0; return C0 + V0 * d * (1 + d / 90.0)
def draw(f, t):
    p = pos(t); ang = 3.0 * np.sin(2 * np.pi * (t - T0) / 28.0)
    M = cv2.getRotationMatrix2D((float(pc[0]), float(pc[1])), ang, 1.0); M[:, 2] += p - pc
    img = cv2.warpAffine(crop, M, (W, H), flags=cv2.INTER_LINEAR).astype(np.float32)
    al = cv2.warpAffine(a, M, (W, H), flags=cv2.INTER_LINEAR)[..., None]
    ramp = min(1.0, (t - T0) / 6.0); ramp = ramp * ramp * (3 - 2 * ramp)
    al = al * ramp
    return np.clip(f * (1 - al) + img * al, 0, 255).astype(np.uint8), al.max()
PLATE = frames[472].astype(np.float32)          # the same spot after the original koi has gone
def deghost(f, t):
    # the AI's own fading copy of this koi: washed-out orange in the lower right while it fades (t 404-470)
    if not (404 <= t <= 470): return f
    hh_ = cv2.cvtColor(np.clip(f, 0, 255).astype(np.uint8), cv2.COLOR_BGR2HSV).astype(int)
    g = (((hh_[..., 0] < 26) | (hh_[..., 0] > 164)) & (hh_[..., 1] > 45) & (hh_[..., 2] > 60)).astype(np.uint8)
    g[:, :1120] = 0; g[:520] = 0
    g = cv2.morphologyEx(g, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    g = cv2.dilate(g, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41)))
    # plus anything that still differs strongly from the clean plate inside the koi's own track box
    d = np.abs(f - PLATE).mean(2)
    box = np.zeros(g.shape, np.uint8); box[560:1080, 1120:1900] = 1
    g2 = ((d > 22) & (box > 0)).astype(np.uint8)
    g2 = cv2.dilate(cv2.morphologyEx(g2, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)), np.ones((21, 21), np.uint8))
    g = np.maximum(g, g2)
    g = cv2.GaussianBlur(g.astype(np.float32), (0, 0), 8)[..., None]
    return f * (1 - g) + PLATE * g
out = []
last = None
for t, f in enumerate(frames):
    if t >= T0:
        g, vis = draw(deghost(f.astype(np.float32), t), t)
        if vis < 0.01 and last is None and t > T0 + 10: last = t
        out.append(g if (last is None) else f)
    else: out.append(f)
print('sprite leaves the frame at', last)
if sheet:
    t_ = [cv2.resize(out[k], (400, 225)) for k in range(396, min(len(out), 560), 8)]
    for i_, k in enumerate(range(396, min(len(out), 560), 8)): cv2.putText(t_[i_], str(k), (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    while len(t_) % 5: t_.append(np.zeros_like(t_[0]))
    cv2.imwrite(dst, np.vstack([np.hstack(t_[r:r + 5]) for r in range(0, len(t_), 5)]), [cv2.IMWRITE_JPEG_QUALITY, 76])
else:
    p = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', '30', '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', '12', '-pix_fmt', 'yuv420p', '-an', dst], stdin=subprocess.PIPE)
    for g in out: p.stdin.write(g.tobytes())
    p.stdin.close(); p.wait(); print('wrote', dst, len(out))
