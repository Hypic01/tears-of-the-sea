# Hero loop pipeline

How the looping hero video was made (Sept 2026). Scripts are one-off tools, kept for reference and reuse. Paths inside them point at the original scratch folder; pass your own paths.

1. Source clip: Wan 3.0 Prime, cover art as both start and end keyframe, static camera, so the clip loops.
2. `loop_retime.py`, `tighten_wrap.py`: trim and retime so the last frame flows into the first.
3. `blink_fix2.py`: make the blinks close fully at the original speed.
4. `widen10.py`: 16:9 expansion. Aleph 2 painted the sides; the original portrait band stays in the middle, joined with a smoothed colour match and a narrow blur heal.
5. `hair_sway2.py`: loop-exact underwater hair sway (periods divide the loop length).
6. `strand_overlay2.py`: connects the loose cheek strands to the hair.
7. `bridge_sides4.py`, `region_bridge.py`, `koi_exit.py`, `redkoi.py`: hide koi that popped, faded or ghosted in the AI-painted sides.
8. `bubbles.py`: loop-exact rising bubbles in the open water.
9. `web_encode.py`: AV1 + H.264 web encodes under 13.5 MB (env `CODECS`, `H264_SCALE`).
10. Tall cut: `ffmpeg -i wide_final2_master.mp4 -vf crop=810:1440:872:0 ...` then `web_encode.py`.

Audits: `audit_koi.py` (grid pops), `audit_blobs.py` (koi born or died mid-loop), `audit_ghost.py` + `gate.py` (face drift, koi count, half-opacity shadows). The audits miss faint ghosts; always review a contact sheet by eye.
