# Mabisyo artist site: design spec

Date: 2026-09-28. Status: approved in chat by Joon, awaiting his review of this file.
Direction chosen: **A, "The insert, unfolded"**. Mockups: `mockups/directions.html` (frames A1 to A4).

## Goal

Turn the one-album concept page into a site that could be Mabisyo's official home: one link for all his
tapes, with The Tears of the Sea as the featured, moving piece. Joon will show it to the artist when it is
finished. Nothing is sold. It stays labeled as a concept until the artist replies.

## Principles

1. Everything comes from the printed cover. Colors: the card's navy `#1A1D2E` and red `#E05252`, plus the
   painting. Off-white `#F3EEE9` only for text that sits on the painting.
2. Type: the title traced from the cover (vector), and Fondamento for all other text. No other fonts.
3. Words: names, numbers and links. The only sentences are the artist's own liner-note quote and the
   concept notice. No slogans.
4. No pill buttons, numbered section labels, fact boxes or filler image tiles. Links are plain red text.
5. **Every album behaves the same.** One art decision applies to all albums.
6. The Dolby mark appears only inside the printed cover image. Rebuilt elements never redraw it.

## Page structure

| # | Section | Content |
|---|---|---|
| 1 | The insert | The cover as printed, centred on `#11131F`. The illustration area is a window onto the video, already playing. "Mabisyo" top left, "Tapes" and "Listen" top right. |
| 2 | The opening | Pinned scroll. The window grows until the video fills the whole screen; the card slides off to the left (Joon, 2026-09-28: a spine cut the title at an odd spot). |
| 3 | The card, flat | Traced title, fold line, A and B letters, eight tracks with lengths, each linking to its Bandcamp track page. One line: "Mabisyo · Chile · 2024" and "Cassette and digital on Bandcamp". |
| 4 | The shelf | All albums as spines cropped from their real covers, newest first. Picking a spine pulls it out: full cover, name, year, track count, link to Bandcamp. |
| 5 | The foot | Credit line and the concept notice. |

## The album rule

Every album opens the same way: the cover sits as printed, and its illustration grows to fill the screen.

- An album with a video: the illustration moves (same video element from first screen to full screen, never
  swapped or restarted).
- An album without a video: the illustration is still.
- Filling a wide screen: **zoom to fill** by default (object-fit cover, focus point set per album).
  An album is AI-widened only when zoom to fill cuts a face or the main subject. The Tears of the Sea is
  already widened.
- Phones: the illustration is tall and the screen is tall, so no widening is needed.

In this round only The Tears of the Sea has the full opening on the home page. Other albums show on the
shelf and link to Bandcamp. Per-album pages that reuse the opening are a later round; the data model and
components must allow it without redesign.

## The window geometry (The Tears of the Sea)

The cover's illustration maps onto the 2560x1440 master at x 815 to 1734, full height. So the window is a
clip of the wide video, and growing the window reveals the painted sides. On phones the tall cut
(`crop=810:1440:872:0`) is used for both states.

## Motion

- One signature moment: the opening (section 2), driven by GSAP ScrollTrigger, pinned, scrubbed.
- Small hover and focus movement on shelf spines.
- Transform, opacity and clip-path only.
- `prefers-reduced-motion`: no pin, no scrub, video hidden, each state shown as a still.

## Data

`data/albums.json`: one entry per album: `slug, title, year, tracks, bandcamp, cover, spineX, focus,
wide (optional), video (optional)`. `spineX` is where the printed spine sits as a fraction of cover width;
covers without a spine use a slice of the art. Adding a tape is one entry plus one image.

## Build

- Static page, no framework, same repo and Vercel project. GSAP and ScrollTrigger from a CDN or vendored.
- Files: `index.html`, `css/site.css`, `js/opening.js`, `js/shelf.js`, `data/albums.json`, `assets/`.
- Built on a branch with a Vercel preview URL. The current site stays live until Joon approves.
- The koi fix is a separate track; the fixed video replaces `assets/hero-*.mp4` when ready (bump `?v=`).

## Out of scope this round

Videos for other albums, an audio player, per-album pages, a store.

## Before it is shown to the artist

- Concept notice visible. First message to him asks, it does not announce.
- Say plainly that the video is AI-animated from his cover and that the sides were AI-extended.
- His Bandcamp notes unauthorized uploads of his work; link every album to his own Bandcamp page.

## Done means

- Desktop 1440x900 and phone 390x844: opening scrubs smoothly both ways, video never restarts, no
  horizontal scroll, no console errors.
- Reduced motion shows stills and all content.
- Every track and album link opens the right Bandcamp page.
- Keyboard: every link and spine reachable, visible focus ring.
- Only the two fonts and three colors above appear in computed styles (checked by script).
