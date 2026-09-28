"""Seamless loop for a start=end AI clip: remove the ease-in/ease-out lull, then blend the join.

Models slow everything down as they approach the shared first/last frame, so a plain loop
shows a pause and restart. Here playback is re-timed near both ends so the motion keeps a
steady pace through the loop point (speed factor = median speed / local speed, capped),
then a short smoothstep blend hides any remaining mismatch at the wrap.

usage: python3 loop_retime.py IN.mp4 OUT_master.mp4 [end_zone_s=3.0] [max_speedup=3.0] [blend_s=0.3]
"""
import sys, subprocess
import cv2
import numpy as np

src, dst = sys.argv[1], sys.argv[2]
zone_s = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
max_up = float(sys.argv[4]) if len(sys.argv) > 4 else 3.0
blend_s = float(sys.argv[5]) if len(sys.argv) > 5 else 0.3

cap = cv2.VideoCapture(src)
fps = cap.get(cv2.CAP_PROP_FPS) or 30
frames = []
while True:
    ok, f = cap.read()
    if not ok:
        break
    frames.append(f)
N = len(frames)
H, W = frames[0].shape[:2]
sm = [cv2.resize(f, (W // 4, H // 4), interpolation=cv2.INTER_AREA).astype(np.float32) for f in frames]
step = np.array([np.abs(sm[i + 1] - sm[i]).mean() for i in range(N - 1)])
speed = np.convolve(step, np.ones(15) / 15, mode='same')
mid = speed[int(N * 0.2):int(N * 0.8)]
m = float(np.median(mid))

zone = zone_s * fps
idx = np.arange(N - 1)
w = np.clip(1 - np.minimum(idx, (N - 2) - idx) / zone, 0, 1)
w = w * w * (3 - 2 * w)                                  # 1 at the very ends, 0 beyond the zone
f_raw = np.clip(m / np.maximum(speed, 1e-3), 1.0, max_up)
factor = 1 + (f_raw - 1) * w


def src_frame(t):
    i = int(np.floor(t))
    if i >= N - 1:
        return frames[N - 1].astype(np.float32)
    a = t - i
    return (1 - a) * frames[i].astype(np.float32) + a * frames[i + 1].astype(np.float32)


times = [0.0]
while True:
    t = times[-1]
    nxt = t + float(np.interp(t, idx, factor))
    if nxt >= N - 1:
        break
    times.append(nxt)
out = [src_frame(t) for t in times]                      # last source frame (== first) is never emitted

k = int(round(blend_s * fps))
if k > 0:
    head = out[:k]
    body = out[k:]
    for j in range(k):                                   # ease the tail into the head so the wrap is continuous
        a = (j + 1) / (k + 1)
        a = a * a * (3 - 2 * a)
        body[len(body) - k + j] = (1 - a) * body[len(body) - k + j] + a * head[j]
    out = body

so = [cv2.resize(np.clip(f, 0, 255).astype(np.uint8), (W // 4, H // 4), interpolation=cv2.INTER_AREA).astype(np.float32) for f in out]
ls = np.array([np.abs(so[(i + 1) % len(so)] - so[i]).mean() for i in range(len(so))])
sec = int(round(fps))
print(f'raw {N} frames, mid speed {m:.2f}; loop {len(out)} frames ({len(out) / fps:.1f}s)')
print('raw   speed per second:', [round(float(step[i * sec:(i + 1) * sec].mean()), 2) for i in range(len(step) // sec)])
print('loop  speed per second:', [round(float(ls[i * sec:(i + 1) * sec].mean()), 2) for i in range(len(ls) // sec)])
print(f'loop  step at wrap {ls[-1]:.2f}  (median {np.median(ls):.2f}, max {ls.max():.2f})')

p = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', f'{fps}', '-i', '-',
                      '-c:v', 'libx264', '-preset', 'slow', '-crf', '12', '-pix_fmt', 'yuv420p', '-an', dst], stdin=subprocess.PIPE)
for f in out:
    p.stdin.write(np.clip(f, 0, 255).astype(np.uint8).tobytes())
p.stdin.close()
p.wait()
cv2.imwrite(dst.replace('.mp4', '_poster.jpg'), np.clip(out[0], 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 88])
