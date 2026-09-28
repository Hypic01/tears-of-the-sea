"""Gate check for a single-source 16:9 loop: face drift, koi count, shadow (semi-transparent koi) score.
usage: python3 gate.py VIDEO.mp4 KEYFRAME.png"""
import sys, cv2, numpy as np
vid, key = sys.argv[1], sys.argv[2]
K = cv2.resize(cv2.imread(key), (640, 360), interpolation=cv2.INTER_AREA)
def hsv(f): return cv2.cvtColor(f, cv2.COLOR_BGR2HSV).astype(int)
hk = hsv(K)
skin = (((hk[..., 0] < 24) | (hk[..., 0] > 166)) & (hk[..., 1] > 30) & (hk[..., 1] < 170))
skin = cv2.dilate(skin.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
eye = cv2.cvtColor(K[110:190, 220:420], cv2.COLOR_BGR2GRAY).astype(np.float32)
c = cv2.VideoCapture(vid); drift = []; counts = []; shadow = []; n = 0
while True:
    ok, f = c.read()
    if not ok: break
    s = cv2.resize(f, (640, 360), interpolation=cv2.INTER_AREA); h = hsv(s)
    (dx, dy), _ = cv2.phaseCorrelate(eye, cv2.cvtColor(s[110:190, 220:420], cv2.COLOR_BGR2GRAY).astype(np.float32))
    drift.append(np.hypot(dx, dy))
    hue = (h[..., 0] < 24) | (h[..., 0] > 166)
    solid = hue & (h[..., 1] > 170) & (h[..., 2] > 120)
    sm_ = cv2.morphologyEx(solid.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    nl, lab, st, _ = cv2.connectedComponentsWithStats(sm_)
    counts.append(sum(1 for k in range(1, nl) if st[k, 4] > 600))
    ghost = hue & (h[..., 1] > 60) & (h[..., 1] <= 150) & (h[..., 2] > 70) & ~skin
    ghost &= ~(cv2.dilate(solid.astype(np.uint8), np.ones((11, 11), np.uint8)) > 0)
    ghost = cv2.morphologyEx(ghost.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)) > 0
    shadow.append(ghost.sum()); n += 1
drift = np.array(drift); counts = np.array(counts); shadow = np.array(shadow)
print(f'{vid}: {n} frames')
print(f'  face drift px (640 scale): median {np.median(drift):.1f}  max {drift.max():.1f}')
print(f'  koi (solid blobs) per frame: median {np.median(counts):.0f}  range {counts.min()}-{counts.max()}')
print(f'  shadow px per frame: median {np.median(shadow):.0f}  p90 {np.percentile(shadow,90):.0f}  max {shadow.max()}')
