"""Fit one colour correction that maps the video's colours onto the original cover's.

Frame 0 of the loop is the cover itself (it was the start keyframe), so the cover is registered onto
frame 0 (SIFT + homography) and a smooth RGB polynomial is fitted from video pixels to cover pixels over
the portrait, trimming pixels that do not correspond (koi or bubbles that moved). The fit is baked into a
33^3 .cube LUT and applied to every frame, so the painted sides move with the middle.

usage: python3 fit_lut.py FRAME0_RGB.png COVER.jpg OUT.cube
"""
import sys, cv2, numpy as np
fr_p, cov_p, out = sys.argv[1:4]
fr = cv2.imread(fr_p); cover = cv2.imread(cov_p)
sift = cv2.SIFT_create(6000)
k1, d1 = sift.detectAndCompute(cv2.cvtColor(cover, cv2.COLOR_BGR2GRAY), None)
k2, d2 = sift.detectAndCompute(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), None)
good = [a for a, b in cv2.BFMatcher().knnMatch(d1, d2, k=2) if a.distance < 0.7 * b.distance]
H, _ = cv2.findHomography(np.float32([k1[a.queryIdx].pt for a in good]), np.float32([k2[a.trainIdx].pt for a in good]), cv2.RANSAC, 4.0)
h, w = fr.shape[:2]
tgt = cv2.warpPerspective(cover, H, (w, h))
valid = cv2.warpPerspective(np.full(cover.shape[:2], 255, np.uint8), H, (w, h)) > 0
valid = cv2.erode(valid.astype(np.uint8), np.ones((25, 25), np.uint8)) > 0
valid[:, :880] = False; valid[:, 1675:] = False            # the original portrait band only

src_b = cv2.GaussianBlur(fr, (0, 0), 2).astype(np.float32) / 255
tgt_b = cv2.GaussianBlur(tgt, (0, 0), 2).astype(np.float32) / 255
X = src_b[valid][:, ::-1]; Y = tgt_b[valid][:, ::-1]          # RGB
rng = np.random.default_rng(0); idx = rng.choice(len(X), min(200000, len(X)), replace=False); X, Y = X[idx], Y[idx]


def feats(x):
    r, g, b = x[:, 0], x[:, 1], x[:, 2]
    return np.stack([np.ones_like(r), r, g, b, r * r, g * g, b * b, r * g, r * b, g * b], 1)


keep = np.ones(len(X), bool)
for it in range(4):                                         # robust: drop the worst-matching pixels and refit
    Wt, *_ = np.linalg.lstsq(feats(X[keep]), Y[keep], rcond=None)
    err = np.linalg.norm(feats(X) @ Wt - Y, axis=1)
    keep = err < np.percentile(err, 80)
    print(f'iter {it}: median err {np.median(err)*255:.1f}/255, kept {keep.mean():.0%}')

N = 33
g = np.linspace(0, 1, N)
b_, g_, r_ = np.meshgrid(g, g, g, indexing='ij')            # .cube order: red fastest
grid = np.stack([r_.ravel(), g_.ravel(), b_.ravel()], 1)
lut = np.clip(feats(grid) @ Wt, 0, 1)
with open(out, 'w') as f:
    f.write(f'TITLE "tears-of-the-sea cover match"\nLUT_3D_SIZE {N}\n')
    for v in lut:
        f.write(f'{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n')
np.save('fit_W.npy', Wt)
print('wrote', out)
