# tears-of-the-sea: agent contract (source of truth)

An unofficial concept site for Mabisyo's beat tape "The Tears of the Sea" (https://mabisyo.bandcamp.com/album/the-tears-of-the-sea). An experiment for the Playground section of Joon Park's portfolio. The cover art is animated as a seamless underwater loop in the hero; the tracklist below fades in side by side.

## Stack

- One static page, no build step: `index.html` (inline CSS and JS) plus `assets/`.
- Hosting: Vercel, account `hypic01`, static deploy of the repo root. `vercel.json` only sets cache headers.
- Fonts: Cinzel Decorative + Cormorant Infant from Google Fonts.

## Commands

```
python3 pipeline/range_server.py 8767      # local preview with HTTP Range (python -m http.server breaks video seeking/looping)
vercel deploy --prod                       # Claude or Joon only
```

## Hero video rules

- ONE master (`masters/wide_final2_master.mp4`, 2560x1440, 533 frames, loops seamlessly). The tall cut is a straight crop of it (`crop=810:1440:872:0`), never a separate render, so every ratio shows the same scene. Joon rejected a version where desktop and phone differed.
- Each cut ships as AV1 (libsvtav1) and H.264, each at most ~13.5 MB, via `pipeline/web_encode.py`. The page picks the cut from the hero's own aspect ratio (ResizeObserver) and AV1 via `canPlayType(...) === 'probably'`.
- `masters/` is gitignored (large). It is the only copy of the finished render; do not delete it.
- Known issue to fix next: faint shadow duplicates of koi along the two vertical seam bands beside her face (x about 873 and 1682 in the master), from two sources blended over the overlap.

## Layout

```
index.html          the site
assets/             served: hero-{wide,tall}.{av1,h264}.mp4, posters, cover.jpg, grain.png
pipeline/           Python (OpenCV + ffmpeg) scripts that built the loop; see pipeline/README.md
canvas/             the original Claude Design canvas source (Main.dc.html), reference only
masters/            local-only render masters (gitignored)
```

## Conventions

- Keep the "Unofficial concept" tag and the footer credit. Music and art belong to Mabisyo and the cover artist.
- Motion: transform and opacity only, respect `prefers-reduced-motion` (the video is hidden and the poster shows).
- Verify in a real browser at desktop (1440x900) and phone (390x844) before calling a change done, including that the video loops without a jump.
