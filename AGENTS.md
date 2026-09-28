# tears-of-the-sea: agent contract (source of truth)

A concept for an artist site for Mabisyo (https://mabisyo.bandcamp.com), built around the beat tape "The Tears of the Sea". An experiment for the Playground section of Joon Park's portfolio, which Joon plans to show the artist when it is finished. The printed cassette cover opens into the moving painting; the card laid flat is the tracklist; every other tape sits on a shelf as its printed spine.

## Stack

- One static page, no build step, no framework: `index.html`, `css/site.css`, `js/opening.js`, `js/shelf.js`, `data/albums.json`, `assets/`.
- Hosting: Vercel, account `hypic01`, static deploy of the repo root. `vercel.json` only sets cache headers. Pushes to `main` deploy to production; other branches get preview URLs.
- Font: Fondamento from Google Fonts. The title is a vector trace of the printed cover (`assets/title.svg`).
- Spec: `docs/superpowers/specs/2026-09-28-artist-site-design.md`. Plan: `.plans/artist-site.md`.

## Commands

```
python3 pipeline/range_server.py 8767 .    # local preview with HTTP Range (python -m http.server breaks video seeking/looping)
python3 tests/site_check.py --links        # files, fonts, colours, album data, every external link
python3 pipeline/fetch_albums.py .         # re-read the artist's Bandcamp into data/albums.json + assets/covers/ (keeps hand-set fields)
vercel deploy --prod                       # Claude or Joon only
```

## Design rules (from the spec, do not drift)

- Colours measured from the printed cover: navy `#161E2E`, deep navy `#0F1420`, red ink `#FF4644`. Off-white `#F3EEE9` only for text that sits on the painting. `tests/site_check.py` fails on any other colour or font.
- Words are names, numbers and links. The only sentences are the artist's own album note and the concept notice. No slogans.
- No pill buttons, numbered section labels, fact boxes or filler tiles. Links are plain red text.
- The Dolby mark appears only inside the printed cover image. Never redraw it.
- Every album behaves the same. Other albums zoom to fill; AI-widen one only when zoom to fill cuts a face.
- Keep the concept notice in the foot until the artist replies. The album credits the cover artist as unknown ("it looks like it was made by an AI"); do not credit the cover to Mabisyo.

## Hero video rules

- ONE master per album. Current: `masters/layered/layered-v3-master.mp4` (2560x1440, 566 frames, 18.9 s loop, BT.709). The tall cut is a straight crop of it, `crop=920:1440:810:0` (the cover's painting area), never a separate render. Joon rejected a version where desktop and phone differed.
- Built in layers, not as one AI video: a fish-free background (`pipeline/plate_prep.py`) with each koi as its own green-screen clip laid on top (`pipeline/layered_build.py`, config `masters/layered/build.json`). One-piece AI video merged, dissolved and cut the fish; do not go back to it.
- Fish stay solid and in front of her hair. A hair mask leaves them half see-through, which reads as a ghost.
- Colour: the background is fitted to the cover (`masters/layered/plate_fit.npy`). Her skin should measure near 243,222,217.
- Decode video with ffmpeg and an explicit BT.709 matrix when a script reads it. OpenCV's own decode shifts the water toward green.
- Each cut ships as AV1 (libsvtav1) and H.264, each at most ~13.5 MB, via `pipeline/web_encode.py`.
- Assets are cached for a week (`vercel.json`), so when a video or poster is replaced, bump the `?v=` on its URLs in `js/opening.js` and `index.html`.
- `masters/` is gitignored (large). It is the only copy of the finished render and its sources; do not delete it.
- Known and accepted for now: a faint rectangle on her skin between her eyes (2 to 3 levels, already in the old video); the background is upscaled from 1080p.

## Layout

```
index.html, css/, js/   the site
data/albums.json        the shelf: one entry per album (slug, title, year, date, tracks, bandcamp, cover, spineX, featured)
assets/                 served: hero-{wide,tall}.{av1,h264}.mp4, posters, card.webp, cover.webp, title.svg, letters, covers/
pipeline/               Python (OpenCV + ffmpeg) that builds the video and the site assets; see pipeline/README.md
tests/site_check.py     static checks
mockups/                the three directions shown to Joon; A was chosen
canvas/                 the original Claude Design canvas source, reference only
masters/                local-only render masters and sources (gitignored)
```

## Conventions

- Keep the "Unofficial concept" tag and the footer credit. Music and art belong to Mabisyo and the cover artist.
- Motion: transform and opacity only, respect `prefers-reduced-motion` (the video is hidden and the poster shows).
- Verify in a real browser at desktop (1440x900) and phone (390x844) before calling a change done, including that the video loops without a jump.
