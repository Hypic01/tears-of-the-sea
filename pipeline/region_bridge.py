"""Replace one screen region with a keyframed AI bridge over a (possibly wrapping) frame window.

usage: python3 region_bridge.py COMPOSITE.mp4 BRIDGE.mp4 T0 T1 X0 Y0 FEATHER OUT.mp4
The region is x >= X0 and y >= Y0 (lower right), feathered by FEATHER px; eased in/out over EDGE frames.
"""
import sys, subprocess
import cv2
import numpy as np
src, brg, T0, T1, X0, Y0, FE, dst = sys.argv[1], sys.argv[2], *map(int, sys.argv[3:8]), sys.argv[8]
EDGE = 10
cb = cv2.VideoCapture(brg); BR = []
while True:
    ok, f = cb.read()
    if not ok: break
    BR.append(f)
nb = len(BR)
cap = cv2.VideoCapture(src); fps = cap.get(cv2.CAP_PROP_FPS) or 30
W = int(cap.get(3)); H = int(cap.get(4)); NF = int(cap.get(7))
xx = np.arange(W, dtype=np.float32); yy = np.arange(H, dtype=np.float32)
wx = np.clip((xx - X0) / FE + 0.5, 0, 1); wy = np.clip((yy - Y0) / FE + 0.5, 0, 1)
wx = wx * wx * (3 - 2 * wx); wy = wy * wy * (3 - 2 * wy)
WR = (wy[:, None] * wx[None, :])[..., None]
def bridge_at(v):
    t = (v - T0) / (T1 - T0) * (nb - 1); j = int(t); a = t - j; j2 = min(j + 1, nb - 1)
    return cv2.resize(BR[j].astype(np.float32) * (1 - a) + BR[j2].astype(np.float32) * a, (W, H), interpolation=cv2.INTER_LANCZOS4)
c2 = cv2.VideoCapture(src); c2.set(1, T0 % NF); _, k0 = c2.read()
m = WR[..., 0] > 0.5
ref = k0[m].reshape(-1, 3).astype(np.float32); got = bridge_at(T0)[m].reshape(-1, 3)
G = ref.std(0) / np.maximum(got.std(0), 1); O = ref.mean(0) - got.mean(0) * G
print('colour gain', np.round(G, 3), 'offset', np.round(O, 1))
pipe = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', f'{fps}', '-i', '-',
                         '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-pix_fmt', 'yuv420p', '-an', dst], stdin=subprocess.PIPE)
i = 0
while True:
    ok, f = cap.read()
    if not ok: break
    v = i if i >= T0 else i + NF
    if T0 <= v <= T1:
        e = min(v - T0, T1 - v) / EDGE; e = float(np.clip(e, 0, 1)); e = e * e * (3 - 2 * e)
        b = bridge_at(v) * G + O
        w = WR * e
        f = np.clip(f.astype(np.float32) * (1 - w) + b * w, 0, 255).astype(np.uint8)
    pipe.stdin.write(f.tobytes()); i += 1
pipe.stdin.close(); pipe.wait(); print('wrote', dst, i, 'frames')
