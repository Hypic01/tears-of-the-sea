"""Write every album page from templates/tape.html and data/tapes/*.json.

The featured album is also written to index.html (the home page). Every album behaves the same: the only
difference between pages is data (colours, lettering, tracks, and whether the illustration moves).

usage: python3 build_pages.py [FEATURED_SLUG]     (run from the repo root)
"""
import sys, json, glob, os, html

FEATURED = sys.argv[1] if len(sys.argv) > 1 else 'the-tears-of-the-sea'
CSS_V, JS_V = 5, 4
tpl = open('templates/tape.html').read()
e = html.escape


def tracks(side):
    return '\n'.join(f'          <li><a href="{e(t["url"])}" target="_blank" rel="noopener"><span class="t">{t["n"] if False else i + 1}. {e(t["title"])}</span><span class="d">{t["length"]}</span></a></li>'
                     for i, t in enumerate(side))


def letter(d, which):
    if d.get('letters'):
        return f'<img class="side-letter" src="/assets/tapes/{d["slug"]}/letter-{which.lower()}.svg" alt="Side {which}">'
    return f'<span class="side-letter side-glyph" role="img" aria-label="Side {which}">{which}</span>'


pages = []
for path in sorted(glob.glob('data/tapes/*.json')):
    d = json.load(open(path)); slug = d['slug']; base = f'/assets/tapes/{slug}'
    v = d.get('video')
    if v:
        q = f'?v={v["v"]}'
        tw = v.get('tallW', 914)
        cfg = dict(slug=slug, wide=dict(av1=f'{base}/hero-wide.av1.mp4{q}', h264=f'{base}/hero-wide.h264.mp4{q}', codec='av01.0.12M.08', poster=f'{base}/poster-wide.jpg{q}', ar=2560 / 1440, a0=v['a0']),
                   tall=dict(av1=f'{base}/hero-tall.av1.mp4{q}', h264=f'{base}/hero-tall.h264.mp4{q}', codec='av01.0.08M.08', poster=f'{base}/poster-tall.jpg{q}', ar=tw / 1440, a0=0))
        still_src = f'{base}/poster-wide.jpg{q}'
        video_tag = '<video class="win-video" muted loop playsinline preload="auto"></video>'
        still_art = (f'<picture>\n      <source media="(max-aspect-ratio: 4/5)" srcset="{base}/poster-tall.jpg{q}">\n'
                     f'      <img class="still-art" src="{base}/poster-wide.jpg{q}" alt="The illustration from the cover, widened: {e(d["coverAlt"])}">\n    </picture>')
    else:
        one = dict(still=f'{base}/art.webp', ar=1144 / 1800, a0=0, focusY=d.get('focusY', 0.5))
        cfg = dict(slug=slug, wide=one, tall=one)
        still_src = f'{base}/art.webp'; video_tag = ''
        still_art = f'<picture>\n      <img class="still-art" src="{base}/art.webp" alt="The illustration from the cover: {e(d["coverAlt"])}">\n    </picture>'
    n = len(d['sideA']) + len(d['sideB'])
    vals = dict(d, pageTitle=(f'{d["title"]} · Mabisyo'), description=f'{d["title"]} by Mabisyo. {n} tracks, {d["released"]}. Beat tapes from Chile.',
                cssV=CSS_V, jsV=JS_V, stillSrc=still_src, videoTag=video_tag, stillArt=still_art, sideA=tracks(d['sideA']), sideB=tracks(d['sideB']),
                letterA=letter(d, 'A'), letterB=letter(d, 'B'), nTracks=n, config=json.dumps(cfg),
                paperStyle=(f' style="background-image:url({base}/paper.jpg)"' if d.get('paper') else ''))
    raw = {'videoTag', 'stillArt', 'sideA', 'sideB', 'letterA', 'letterB', 'config', 'paperStyle'}
    page = tpl
    for k, val in vals.items():
        if isinstance(val, (dict, list)):
            continue
        page = page.replace('{{' + k + '}}', str(val) if k in raw else e(str(val), quote=True))
    assert '{{' not in page, [x for x in page.split('{{')[1:]][:3]
    os.makedirs(f'tape/{slug}', exist_ok=True)
    open(f'tape/{slug}/index.html', 'w').write(page)
    if slug == FEATURED:
        open('index.html', 'w').write(page.replace('<title>' + e(vals['pageTitle']) + '</title>', '<title>Mabisyo</title>'))
    pages.append(slug)
print('pages:', pages, 'home:', FEATURED)
