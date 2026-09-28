"""Join start=end AI background clips into one loop without the pause, the soft frames or the stutter.

Each clip starts and ends on the same still. The model eases into that still (a few frozen frames at the
end), comes out of it soft (about ten blurry frames at the start) and paces its frames unevenly (a bigger
step every fifth frame). So for every clip:
  1. even out the pacing: re-time so motion per frame follows a smoothed curve (flow-interpolated frames)
  2. drop the soft head and the frozen tail (keep frames HEAD..TAIL)
  3. bridge from this clip's last kept frame to the next clip's first kept frame with BRIDGE in-between
     frames made by optical flow, so hair moves across the join instead of cross-fading

usage: python3 plate_prep.py OUT.mkv CLIP_A.mp4 CLIP_B.mp4 [...]      (writes lossless FFV1)
"""
import sys, subprocess
import cv2
import numpy as np

out, clips = sys.argv[1], sys.argv[2:]
HEAD, TAIL, BRIDGE = 12, 288, 6        # 6 in-betweens keeps the hair at its normal speed across the join
dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)


def read(p):
    cap = cv2.VideoCapture(p); F = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        F.append(f)
    return F


def between(f0, f1, a):
    """frame a of the way from f0 to f1, moved along the optical flow"""
    if a <= 1e-3:
        return f0.astype(np.float32)
    if a >= 1 - 1e-3:
        return f1.astype(np.float32)
    g0, g1 = cv2.cvtColor(f0, cv2.COLOR_BGR2GRAY), cv2.cvtColor(f1, cv2.COLOR_BGR2GRAY)
    fw = dis.calc(g0, g1, None); bw = dis.calc(g1, g0, None)
    fw = cv2.GaussianBlur(fw, (0, 0), 9); bw = cv2.GaussianBlur(bw, (0, 0), 9)     # raw flow on brushwork is noisy and tears the paint
    h, w = g0.shape
    xx, yy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    a0 = cv2.remap(f0, xx - a * fw[..., 0], yy - a * fw[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    a1 = cv2.remap(f1, xx - (1 - a) * bw[..., 0], yy - (1 - a) * bw[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    # both sources are moved to the in-between position, so they already agree; mix them only around the
    # middle (a plain a/1-a mix of two warps goes soft)
    b = float(np.clip((a - 0.3) / 0.4, 0, 1)); b = b * b * (3 - 2 * b)
    m = (1 - b) * a0.astype(np.float32) + b * a1.astype(np.float32)
    return m


kept = []
for p in clips:
    F = read(p)
    sm = [cv2.resize(f, (480, 270), interpolation=cv2.INTER_AREA).astype(np.float32) for f in F]
    step = np.array([np.abs(sm[i + 1] - sm[i]).mean() for i in range(len(F) - 1)])
    c = np.r_[0, np.cumsum(step)]                                  # how far the scene has moved by each frame
    k = np.ones(11) / 11
    target = np.convolve(np.pad(c, 5, mode='reflect', reflect_type='odd'), k, mode='valid')   # the same curve, evened out
    target = np.clip(target, c[0], c[-1])
    src_t = np.interp(target, c, np.arange(len(F)))                # which source time shows that much movement
    frames = []
    for i in range(HEAD, TAIL + 1):
        t = float(src_t[i]); j = min(int(np.floor(t)), len(F) - 2)
        frames.append(between(F[j], F[j + 1], t - j))
    shift = np.abs(src_t - np.arange(len(F)))[HEAD:TAIL + 1]
    print(p, 'frames', len(F), 'kept', len(frames), 're-timed by up to %.2f frames' % shift.max())
    kept.append(frames)

seq = []
for n, frames in enumerate(kept):
    seq += frames
    nxt = kept[(n + 1) % len(kept)]
    a, b = np.clip(frames[-1], 0, 255).astype(np.uint8), np.clip(nxt[0], 0, 255).astype(np.uint8)
    for j in range(1, BRIDGE + 1):
        seq.append(between(a, b, j / (BRIDGE + 1)))
h, w = seq[0].shape[:2]
pipe = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{w}x{h}', '-r', '30', '-i', '-',
                         '-c:v', 'ffv1', '-pix_fmt', 'bgr0', out], stdin=subprocess.PIPE)
for f in seq:
    pipe.stdin.write(np.clip(f, 0, 255).astype(np.uint8).tobytes())
pipe.stdin.close(); pipe.wait()
sm = [cv2.resize(np.clip(f, 0, 255).astype(np.uint8), (480, 270), interpolation=cv2.INTER_AREA).astype(np.float32) for f in seq]
d = np.array([np.abs(sm[(i + 1) % len(sm)] - sm[i]).mean() for i in range(len(sm))])
lap = np.array([cv2.Laplacian(cv2.cvtColor(np.clip(f, 0, 255).astype(np.uint8)[300:800, 650:1300], cv2.COLOR_BGR2GRAY), cv2.CV_32F).var() for f in seq])
print('loop frames', len(seq), 'median step %.2f' % np.median(d), 'min %.2f max %.2f' % (d.min(), d.max()))
L = len(kept[0])
for name, i in [('join', L - 1), ('loop point', len(seq) - BRIDGE - 1)]:
    ix = [(i - 4 + k) % len(seq) for k in range(BRIDGE + 9)]
    print(name, 'steps', np.round(d[ix], 2)); print(name, 'sharpness', np.round(lap[ix]).astype(int))
print('frames softer than 70% of median:', [int(i) for i in np.where(lap < 0.7 * np.median(lap))[0]])
print('face sharpness min %.0f median %.0f' % (lap.min(), np.median(lap)), 'every-5th-frame ratio %.2f' % max(d[k::5].mean() for k in range(5)) , '/ %.2f' % d.mean())
