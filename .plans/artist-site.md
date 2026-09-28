# Mabisyo artist site: implementation plan

> Executed inline by Claude in the session that wrote it (design-led frontend, per AGENTS routing). Steps use checkboxes.

**Goal:** Replace the one-album concept page with the artist site from direction A: the printed insert opens into the moving painting, the card laid flat is the tracklist, and his other tapes sit on a shelf.

**Spec:** `docs/superpowers/specs/2026-09-28-artist-site-design.md`. Mockups: `mockups/directions.html` (A1 to A4).

**Architecture:** One static page. A sticky full-screen stage holds the cover card and a video "window"; scroll progress `p` (0 to 1) drives transform and clip-path on both. Sections below are normal flow. The shelf is rendered from `data/albums.json`.

**Tech stack:** HTML, CSS, vanilla JS. No build step, no framework. Fondamento from Google Fonts. Python scripts for assets.

## Global constraints (from the spec)

- Colors: navy `#1A1D2E`, deep navy `#11131F`, red `#E05252`; off-white `#F3EEE9` only for text on the painting.
- Type: traced title (SVG) and Fondamento. No other fonts.
- Words: names, numbers, links. Only sentences: the liner-note quote and the concept notice.
- No pill buttons, numbered section labels, fact boxes, filler tiles. Links are plain red text.
- The Dolby mark appears only inside the printed cover image.
- Every album behaves the same; other albums zoom to fill.
- Video: one master per album; the tall cut is a crop of the wide one. BT.709 tags. Bump `?v=` when replaced.
- `prefers-reduced-motion`: no scrub, no video; stills.

## Deviation from the spec (decided while planning)

- **No GSAP.** The opening is one scrubbed value, so `position: sticky` plus a scroll listener with a smoothed `p` does it with no dependency and no pin-spacer jumps. Same look.
- **Shelf spines animate `width`** when one opens (layout, not transform). It is one small row, and clip-path cannot push neighbours aside.
- **No "now playing" track label** on the opened painting (mockup A2 had one). The page has no audio, so the label would claim something false.

## Files

| File | Responsibility |
|---|---|
| `index.html` | Markup for stage, tracklist card, shelf, foot. No inline logic. |
| `css/site.css` | All styles, tokens on `:root`. |
| `js/opening.js` | Stage geometry, scroll progress, video source choice, reduced motion. |
| `js/shelf.js` | Render shelf from `data/albums.json`, selection, keyboard. |
| `data/albums.json` | One entry per album. |
| `assets/hero-{wide,tall}.{av1,h264}.mp4`, `assets/poster-{wide,tall}.jpg` | Hero video v3 (`?v=3`). |
| `assets/card.webp` | Left panel of the printed cover (656x1800 source). |
| `assets/cover.webp` | Whole printed cover, for the shelf and link previews. |
| `assets/title.svg`, `assets/letter-a.svg`, `assets/letter-b.svg` | Traced lettering. |
| `assets/paper.jpg` | Card paper texture tile. |
| `assets/covers/<slug>.webp` | Other albums' covers, 800px. |
| `pipeline/make_site_assets.py` | Builds card, cover, title trace, paper from the cover; encodes nothing. |
| `pipeline/fetch_albums.py` | Reads the artist's Bandcamp, writes covers and a draft `data/albums.json`. |
| `tests/site_check.py` | Static checks: links, fonts, colors, files exist, JSON valid. |

## Tasks

### 1. Hero video and cover assets
- [ ] Encode v3: wide 2560x1440 from `masters/layered/layered-v3-master.mp4`; tall = `crop=920:1440:810:0` (the cover's painting area, so the window matches the print). `pipeline/web_encode.py`, cap 13.5 MB each.
- [ ] Posters from frame 0 of each.
- [ ] `make_site_assets.py`: `card.webp` (cover x 0..656), `cover.webp`, `paper.jpg`, `title.svg` (contour trace of the red title, 4x upscaled mask, evenodd), copy letters.
- Verify: `ffprobe` shows 566 frames and bt709 on all four; `title.svg` renders and matches the printed title when overlaid (checked by eye at 3x).

### 2. Album data
- [ ] `fetch_albums.py`: for each album on `mabisyo.bandcamp.com/music` read title, URL, release date, track count (JSON-LD), download the cover to `assets/covers/<slug>.webp`.
- [ ] Set `spineX` and `focus` per album by eye from a ruled contact sheet; covers with no printed spine get a slice of the art.
- Verify: `albums.json` has every album on the page, newest first; every `bandcamp` URL returns 200.

### 3. Page shell, tokens, tracklist card, foot
- [ ] `index.html` + `css/site.css`: nav, stage placeholder, card section (title, fold line, A and B, eight tracks with lengths linking to Bandcamp track pages, meta line, liner quote), foot with credit and concept notice.
- Verify at 1440x900 and 390x844: no horizontal scroll, focus rings visible, track links correct.

### 4. The opening
- [ ] `js/opening.js`: geometry from viewport (cover size `S`, slot rect, video box = rendered video size), `p` from the sticky section's scroll, smoothed; apply transform + clip-path to the video box, transform to the card, fade the cover's shadow plate; nav color flips at `p > 0.5`.
- [ ] Source choice: tall when viewport is portrait, AV1 when `canPlayType` says probably.
- [ ] Reduced motion / no JS: stage is not sticky; cover still, then full-bleed poster.
- Verify: at `p` = 0, 0.5, 1 on both sizes the video never restarts (`currentTime` keeps rising), painting in the slot lines up with the print, no console errors.

### 5. The shelf
- [ ] `js/shelf.js`: render spines, newest first, Tears selected; click or Enter/Space opens one (others close); info line shows title, year, track count, link to Bandcamp.
- [ ] Horizontal scroll with snap on narrow screens.
- Verify: keyboard only can reach and open every spine; every link opens the right album.

### 6. Checks, preview deploy
- [ ] `tests/site_check.py` passes (fonts limited to Fondamento + fallback, colors limited to the tokens, all local files referenced exist, all external links 200).
- [ ] Push branch `redesign/artist-site`; Vercel builds a preview URL. `main` and the live site stay as they are.
- [ ] Update `AGENTS.md` (layout, hero rules now point at the layered build).

## Definition of done

The spec's "Done means" list, checked on the preview URL at 1440x900 and 390x844, plus reduced motion.
