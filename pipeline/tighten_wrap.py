"""Remove the leftover hesitation just before a loop's wrap by dropping near-duplicate frames.

The model freezes its last second; retiming caps the speed-up, so a few frames before the
wrap still crawl. Frames are chosen on REF (full-frame loop) and the same indices are dropped
from every other frame-aligned render (e.g. an upscaled crop), so all cuts stay in sync.

usage: python3 tighten_wrap.py REF.mp4 IN1.mp4:OUT1.mp4 [IN2.mp4:OUT2.mp4 ...]
env: TAIL (frames before the wrap to inspect, default 40), SLOW (fraction of median counted as a crawl, default 0.6)
"""
import os, sys, subprocess
import cv2
import numpy as np

ref = sys.argv[1]
pairs = [a.split(':') for a in sys.argv[2:]]
tail = int(os.environ.get('TAIL', 40))
slow = float(os.environ.get('SLOW', 0.6))


def small_frames(path, size=(270, 480)):
    cap = cv2.VideoCapture(path)
    out = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        w, h = f.shape[1], f.shape[0]
        sz = size if h > w else (size[1], size[0])
        out.append(cv2.resize(f, sz, interpolation=cv2.INTER_AREA).astype(np.float32))
    return out


s = small_frames(ref)
n = len(s)
d = lambda a, b: float(np.abs(s[b % n] - s[a % n]).mean())
st = np.array([d(i, i + 1) for i in range(n)])
med = float(np.median(st))
start = n - tail
# local pace: what the motion looks like right after the wrap, where playback is steady
target = float(np.median(st[:30]))

keep = list(range(start))
last = start - 1
i = start
while i < n:
    if st[i] >= slow * med or i == n - 1:
        keep.append(i)
        last = i
        i += 1
        continue
    # crawling: jump ahead to the furthest frame that stays within the steady pace
    j = i
    while j + 1 < n and d(last, j + 1) <= target:
        j += 1
    keep.append(j)
    last = j
    i = j + 1
keep = sorted(set(keep))
drop = [i for i in range(n) if i not in keep]
new = [d(keep[k], keep[(k + 1) % len(keep)]) for k in range(len(keep))]
roll = np.convolve(np.concatenate([new[-30:], new[:30]]), np.ones(5) / 5, mode='valid')
print(f'{ref}: {n} frames, median step {med:.2f}, steady pace after wrap {target:.2f}')
print(f'dropping {len(drop)} frames: {drop} -> loop {len(keep)} frames ({len(keep) / 30:.2f}s)')
print('steps across the wrap now:', ' '.join(f'{x:.2f}' for x in new[-14:]), '|', ' '.join(f'{x:.2f}' for x in new[:4]))
print(f'min 5-frame avg across the wrap: {roll.min():.2f} (was a dip to about a quarter of the median)')

keep_set = set(keep)
for src, dst in pairs:
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    p = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', f'{fps}',
                         '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', '12', '-pix_fmt', 'yuv420p', '-an', dst], stdin=subprocess.PIPE)
    idx = 0
    first = None
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if idx in keep_set:
            p.stdin.write(f.tobytes())
            if first is None:
                first = f
        idx += 1
    p.stdin.close()
    p.wait()
    assert idx == n, f'{src} has {idx} frames, reference has {n}: not frame-aligned'
    cv2.imwrite(dst.replace('.mp4', '_poster.jpg'), first, [cv2.IMWRITE_JPEG_QUALITY, 86])
    print(f'wrote {dst} ({W}x{H})')
