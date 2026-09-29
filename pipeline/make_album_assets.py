"""Cut one album's site pieces out of its printed cover and write its page data.

Every Mabisyo cassette cover uses the same template: a card panel on the left 36.4% (tracklist, then the
title running down its right edge) and the illustration on the right. From the cover this makes:
  assets/tapes/<slug>/card.webp    the card panel as printed
  assets/tapes/<slug>/cover.webp   the whole cover
  assets/tapes/<slug>/art.webp     the illustration alone
  assets/tapes/<slug>/paper.jpg    a text-free strip of the card, tiled as the page ground
  assets/tapes/<slug>/title.svg    the title lettering, traced
  data/tapes/<slug>.json           colours measured from the card, tracks split into sides, dates, links

usage: python3 make_album_assets.py SLUG [title_x0 title_x1]     (title strip as fractions of cover width)
reads masters/albums/<slug>/cover.png and masters/albums/<slug>/bandcamp.json; keeps hand-set fields in an existing json
"""
import sys, os, json, re
from email.utils import parsedate_to_datetime
import cv2
import numpy as np

slug = sys.argv[1]
tx0, tx1 = (float(sys.argv[2]), float(sys.argv[3])) if len(sys.argv) > 3 else (0.262, 0.345)
src = f'masters/albums/{slug}'
im = cv2.imread(f'{src}/cover.png')
H, W = im.shape[:2]
CW = int(round(W * 656 / 1800))
out = f'assets/tapes/{slug}'; os.makedirs(out, exist_ok=True); os.makedirs('data/tapes', exist_ok=True)
cv2.imwrite(f'{out}/card.webp', im[:, :CW], [cv2.IMWRITE_WEBP_QUALITY, 90])
cv2.imwrite(f'{out}/cover.webp', cv2.resize(im, (1200, 1200), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_WEBP_QUALITY, 88])
cv2.imwrite(f'{out}/art.webp', im[:, CW:], [cv2.IMWRITE_WEBP_QUALITY, 90])

card = cv2.rotate(im[:, :CW], cv2.ROTATE_90_COUNTERCLOCKWISE).astype(np.float32)      # reads left to right
ground = np.median(card.reshape(-1, 3), 0)                                            # the card's own colour
# the page ground: the cleanest text-free strip of the card. If every strip has lettering in it, the page
# uses the flat card colour instead (a texture with words in it repeats as wallpaper).
d0 = (np.linalg.norm(card - ground, axis=2) > 60).astype(np.float32)
best = None
for yy in range(4, CW - 94, 6):
    for xx in range(0, H - 1200, 40):
        s = float(d0[yy:yy + 90, xx:xx + 1200].mean())
        if best is None or s < best[0]:
            best = (s, yy, xx)
paper = best[0] < 0.004
if paper:
    cv2.imwrite(f'{out}/paper.jpg', card[best[1]:best[1] + 90, best[2]:best[2] + 1200].astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 90])
elif os.path.exists(f'{out}/paper.jpg'):
    os.remove(f'{out}/paper.jpg')

# the title strip: ink is whatever differs most from the card's ground
y0, y1 = int(CW - tx1 * W), int(CW - tx0 * W)
strip = card[max(y0, 0):y1]
dist = np.linalg.norm(strip - ground, axis=2)
ink = np.median(strip[dist >= 0.9 * np.percentile(dist, 99)], 0)
a = np.clip(dist / max(np.linalg.norm(ink - ground), 1), 0, 1)
UP = 4
m = cv2.GaussianBlur(cv2.resize(a, None, fx=UP, fy=UP, interpolation=cv2.INTER_CUBIC), (0, 0), 1.6)
m = (m > 0.5).astype(np.uint8)
m = cv2.copyMakeBorder(m, 16, 16, 16, 16, cv2.BORDER_CONSTANT, value=0)
n, lab, st, _ = cv2.connectedComponentsWithStats(m)
keep = [k for k in range(1, n) if st[k, 4] > 120 * UP]                                 # letters, not paper specks
m = np.isin(lab, keep).astype(np.uint8)
ys, xs = np.where(m > 0)
m = np.ascontiguousarray(m[ys.min() - 8:ys.max() + 8, xs.min() - 8:xs.max() + 8])
cs, _ = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
d = ['M' + ' L'.join(f'{x:.2f} {y:.2f}' for x, y in cv2.approxPolyDP(c, 0.6, True).reshape(-1, 2) / UP) + ' Z' for c in cs if cv2.contourArea(c) >= 30]
hexc = lambda c: '#%02X%02X%02X' % (int(round(c[2])), int(round(c[1])), int(round(c[0])))
bc = json.load(open(f'{src}/bandcamp.json'))
open(f'{out}/title.svg', 'w').write(
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {m.shape[1] / UP:.2f} {m.shape[0] / UP:.2f}" role="img" aria-label="{bc["title"]}">'
    f'<path fill="{hexc(ink)}" fill-rule="evenodd" d="{" ".join(d)}"/></svg>')


def lum(c):
    v = [(x / 255) / 12.92 if x / 255 <= 0.03928 else ((x / 255 + 0.055) / 1.055) ** 2.4 for x in (c[2], c[1], c[0])]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]
contrast = (max(lum(ink), lum(ground)) + 0.05) / (min(lum(ink), lum(ground)) + 0.05)
dur = lambda s: (lambda mm: f'{int(mm.group(1)) * 60 + int(mm.group(2))}:{int(mm.group(3)):02d}')(re.match(r'P(\d+)H(\d+)M(\d+)S', s))
tracks = [dict(n=t[0], title=t[1], length=dur(t[2]), url=t[3]) for t in bc['tracks']]
half = (len(tracks) + 1) // 2
path = f'data/tapes/{slug}.json'
old = json.load(open(path)) if os.path.exists(path) else {}
dt = parsedate_to_datetime(bc['date'])
data = dict(old)
data.update(slug=slug, title=bc['title'], released=f'{dt.day} {dt.strftime("%B %Y")}', year=dt.year,
            bandcamp=f'https://mabisyo.bandcamp.com/album/{slug}', ground=hexc(ground), deep=hexc(ground * 0.68), ink=hexc(ink),
            sideA=tracks[:old.get('splitAt', half)], sideB=tracks[old.get('splitAt', half):],
            title_w=round(m.shape[1] / UP), title_h=round(m.shape[0] / UP), paper=bool(paper))
json.dump(data, open(path, 'w'), indent=1, ensure_ascii=False)
print(slug, 'ground', data['ground'], 'ink', data['ink'], 'contrast %.1f' % contrast, 'title', data['title_w'], 'x', data['title_h'], 'paths', len(d), 'sides', len(data['sideA']), len(data['sideB']))
