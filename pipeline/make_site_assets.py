"""Cut the site's static pieces out of the printed cover: the card panel, the whole cover, the paper
texture and a vector trace of the title lettering.

usage: python3 make_site_assets.py COVER.jpg ASSETS_DIR
"""
import sys
import cv2
import numpy as np

cover_p, out = sys.argv[1], sys.argv[2].rstrip('/')
im = cv2.imread(cover_p)
H, W = im.shape[:2]
CARD_W = 656                                   # the card panel ends here; the painting starts
cv2.imwrite(f'{out}/card.webp', im[:, :CARD_W], [cv2.IMWRITE_WEBP_QUALITY, 90])
cv2.imwrite(f'{out}/cover.webp', cv2.resize(im, (1200, 1200), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_WEBP_QUALITY, 88])

card = cv2.rotate(im[:, :CARD_W], cv2.ROTATE_90_COUNTERCLOCKWISE)      # reads left to right
cv2.imwrite(f'{out}/paper.jpg', card[560:650, 300:1500], [cv2.IMWRITE_JPEG_QUALITY, 90])

# title: red ink on navy. Mask at 4x, trace the outlines, write one evenodd path.
f = card.astype(np.float32)
ink = np.clip((f[..., 2] - np.maximum(f[..., 0], f[..., 1]) - 40) / 110, 0, 1)[60:215, 300:1600]
UP = 4
m = cv2.resize(ink, None, fx=UP, fy=UP, interpolation=cv2.INTER_CUBIC)
m = cv2.GaussianBlur(m, (0, 0), 1.6)
m = (m > 0.5).astype(np.uint8)
m = cv2.copyMakeBorder(m, 16, 16, 16, 16, cv2.BORDER_CONSTANT, value=0)
ys, xs = np.where(m > 0)
m = np.ascontiguousarray(m[ys.min() - 8:ys.max() + 8, xs.min() - 8:xs.max() + 8])
cs, _ = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
d = []
for c in cs:
    if cv2.contourArea(c) < 30:
        continue
    c = cv2.approxPolyDP(c, 0.6, True).reshape(-1, 2) / UP
    d.append('M' + ' L'.join(f'{x:.2f} {y:.2f}' for x, y in c) + ' Z')
h, w = m.shape[0] / UP, m.shape[1] / UP
open(f'{out}/title.svg', 'w').write(
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.2f} {h:.2f}" role="img" aria-label="The Tears of the Sea">'
    f'<path fill="#FF4644" fill-rule="evenodd" d="{" ".join(d)}"/></svg>')
print('title.svg', round(w), 'x', round(h), 'paths', len(d), 'bytes', sum(len(x) for x in d))
