"""Read the artist's Bandcamp and write the shelf data: one cover per album and a draft albums.json.

Keeps any hand-set fields (spineX, focus, wide, video) already in albums.json; only fills what is missing.

usage: python3 fetch_albums.py SITE_ROOT
"""
import sys, re, json, html, os, time, urllib.request
import cv2
import numpy as np

root = sys.argv[1].rstrip('/')
BASE = 'https://mabisyo.bandcamp.com'
UA = {'User-Agent': 'Mozilla/5.0'}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()


page = get(BASE + '/music').decode('utf-8', 'ignore')
slugs = []
for li in re.findall(r'<li data-item-id="album-\d+".*?</li>', page, re.S):
    slugs.append(re.search(r'href="(/album/[^"]+)"', li).group(1))
# albums past the first screen are listed in a data attribute
more = re.search(r'data-client-items="([^"]+)"', page)
if more:
    for it in json.loads(html.unescape(more.group(1))):
        if it.get('type') == 'album' and it.get('page_url') not in slugs:
            slugs.append(it['page_url'])
print(len(slugs), 'albums')

path = f'{root}/data/albums.json'
old = {a['slug']: a for a in json.load(open(path))} if os.path.exists(path) else {}
os.makedirs(f'{root}/assets/covers', exist_ok=True)
out = []
for href in slugs:
    slug = href.split('/')[-1]
    t = get(BASE + href).decode('utf-8', 'ignore')
    ld = json.loads(re.search(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', t, re.S).group(1))
    img = ld.get('image'); img = img[0] if isinstance(img, list) else img
    a = dict(slug=slug, title=ld['name'], year=int(re.search(r'(\d{4})', ld['datePublished']).group(1)), date=ld['datePublished'],
             tracks=int(ld.get('numTracks') or len(ld.get('track', {}).get('itemListElement', []))), bandcamp=BASE + href,
             cover=f'assets/covers/{slug}.webp')
    dst = f'{root}/{a["cover"]}'
    if not os.path.exists(dst):
        im = cv2.imdecode(np.frombuffer(get(img), np.uint8), cv2.IMREAD_COLOR)
        cv2.imwrite(dst, cv2.resize(im, (800, 800), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_WEBP_QUALITY, 86])
    for k in ('spineX', 'focus', 'wide', 'video', 'tall'):
        if k in old.get(slug, {}):
            a[k] = old[slug][k]
    out.append(a); print(a['year'], a['tracks'], a['title'])
    time.sleep(0.4)
from email.utils import parsedate_to_datetime
out.sort(key=lambda a: parsedate_to_datetime(a['date']), reverse=True)
os.makedirs(f'{root}/data', exist_ok=True)
json.dump(out, open(path, 'w'), indent=1, ensure_ascii=False)
print('wrote', path, len(out))
