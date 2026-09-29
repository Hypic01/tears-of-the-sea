"""Static checks for the site. Run from the repo root: python3 tests/site_check.py [--links]

- every local file the page references exists
- only the allowed fonts and colours appear in the stylesheet
- albums.json is valid, newest first, every cover exists
- with --links: every external link answers 200
"""
import json, os, re, sys, urllib.request
from email.utils import parsedate_to_datetime

fail = []
import glob
pages = ['index.html'] + sorted(glob.glob('tape/*/index.html'))
html = '\n'.join(open(p).read() for p in pages); css = open('css/site.css').read(); js = open('js/opening.js').read() + open('js/shelf.js').read()

refs = set(re.findall(r'(?:src|href|srcset)="([^"#]+)"', html)) | set(re.findall(r'"(/assets/[^"]+)"', html)) | set(re.findall(r"'(/(?:assets|data)/[^']+)'", js)) | set(re.findall(r'url\((/assets/[^)]+)\)', html))
for r in sorted(refs):
    if r.startswith(('http', 'data:', 'mailto:')):
        continue
    path = r.split('?')[0].lstrip('/')
    if path.endswith('/') or path == '':
        path += 'index.html'
    if not os.path.exists(path):
        fail.append('missing file: ' + path)

fonts = set(re.findall(r"font(?:-family)?:[^;}]*?'([^']+)'", css)) | set(re.findall(r"--f:'([^']+)'", css))
if fonts - {'Fondamento'}:
    fail.append('unexpected fonts: %s' % (fonts - {'Fondamento'}))
allowed = {'#161e2e', '#0f1420', '#ff4644', '#f3eee9'}
hexes = {h.lower() for h in re.findall(r'#[0-9a-fA-F]{6}\b', css)}
if hexes - allowed:
    fail.append('unexpected colours: %s' % (hexes - allowed))
for rgb in set(re.findall(r'rgba?\(([^)]+)\)', css)):
    c = tuple(int(float(x)) for x in rgb.split(',')[:3])
    if c not in {(0, 0, 0), (255, 255, 255), (15, 20, 32)}:
        fail.append('unexpected rgb colour: ' + rgb)

al = json.load(open('data/albums.json'))
dates = [parsedate_to_datetime(a['date']) for a in al]
if dates != sorted(dates, reverse=True):
    fail.append('albums.json is not newest first')
for a in al:
    for k in ('slug', 'title', 'year', 'tracks', 'bandcamp', 'cover', 'spineX'):
        if k not in a:
            fail.append(f"{a.get('slug')}: no {k}")
    if not os.path.exists(a['cover']):
        fail.append('missing cover: ' + a['cover'])
for a in al:
    if a.get('page') and not os.path.exists(f"tape/{a['slug']}/index.html"):
        fail.append('no page for ' + a['slug'])
print('on the shelf', sum(1 for a in al if a.get('shelf')), 'with pages', sum(1 for a in al if a.get('page')))

banned = re.findall(r'\b(?:delve|leverage|passionate|robust|utilize|seamless|journey)\b|[—–]', re.sub(r'<script.*?</script>', '', html, flags=re.S))
if banned:
    fail.append('copy check: %s' % set(banned))

if '--links' in sys.argv:
    links = sorted(set(re.findall(r'href="(https?://[^"]+)"', html)) | {a['bandcamp'] for a in al})
    links = [l for l in links if 'fonts.g' not in l]
    for l in links:
        try:
            code = urllib.request.urlopen(urllib.request.Request(l, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30).status
        except Exception as e:
            code = getattr(e, 'code', str(e))
        if code != 200:
            fail.append(f'{code} {l}')
    print(len(links), 'links checked')

print('albums', len(al), 'local refs', len(refs))
print('FAIL\n  ' + '\n  '.join(fail) if fail else 'PASS')
sys.exit(1 if fail else 0)
