"""Connect the loose cheek strands to the hair: overlay AI-painted strands (lifted from one edited frame).

The edited still (aligned to frame REF of the composite) differs from the frame only where new strands
were painted; those darker pixels become a strand layer (colour + alpha). The layer sits on every frame,
behind any koi passing in front, and the later hair sway moves it together with the rest of the hair.

usage: python3 strand_overlay.py IN.mp4 OUT.mp4 [sheet]
"""
import sys, subprocess
import cv2
import numpy as np

src, dst = sys.argv[1], sys.argv[2]
sheet = 'sheet' in sys.argv[3:]
B = 'strands/'
base = cv2.imread(B + 'f300.png').astype(np.float32)
edit = cv2.imread(B + 'nb_al.png').astype(np.float32)
mask = cv2.GaussianBlur(cv2.imread(B + 'mask300.png', 0).astype(np.float32) / 255, (0, 0), 12)

lb = cv2.cvtColor(base.astype(np.uint8), cv2.COLOR_BGR2LAB)[..., 0].astype(np.float32)
le = cv2.cvtColor(edit.astype(np.uint8), cv2.COLOR_BGR2LAB)[..., 0].astype(np.float32)
alpha = np.clip((lb - le - 10) / 45, 0, 1) * mask
alpha = cv2.GaussianBlur(alpha, (0, 0), 0.8)
color = edit
print('strand layer coverage %.2f%% of frame' % (100 * (alpha > 0.3).mean()))


def koi(f):
    h = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
    m = (((h[..., 0] < 22) | (h[..., 0] > 168)) & (h[..., 1] > 140) & (h[..., 2] > 110)).astype(np.uint8)
    m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (101, 101)))
    return cv2.GaussianBlur(m.astype(np.float32), (0, 0), 10)


cap = cv2.VideoCapture(src)
fps = cap.get(cv2.CAP_PROP_FPS) or 30
W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
if not sheet:
    pipe = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', f'{fps}',
                             '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-pix_fmt', 'yuv420p', '-an', dst], stdin=subprocess.PIPE)
shots = []
i = 0
while True:
    ok, f = cap.read()
    if not ok:
        break
    # hide a strand only where something now covers that spot (a koi, a fin, a bubble): the frame differs
    # from the reference frame there. Elsewhere the strand stays, so nothing flickers as koi pass nearby.
    d = cv2.GaussianBlur(np.abs(f.astype(np.float32) - base).mean(2), (0, 0), 3)
    occ = np.clip((d - 22) / 26, 0, 1)
    occ = cv2.GaussianBlur(occ, (0, 0), 4)
    a = (alpha * (1 - occ))[..., None]
    g = np.clip(f * (1 - a) + color * a, 0, 255).astype(np.uint8)
    if sheet and i in (0, 150, 300, 446):
        shots.append(g)
    if not sheet:
        pipe.stdin.write(g.tobytes())
    i += 1
if sheet:
    rows = [np.hstack([s[620:1100, 520:1080], s[620:1100, 1480:2040]]) for s in shots]
    cv2.imwrite(dst, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print('sheet', dst)
else:
    pipe.stdin.close(); pipe.wait()
    print('wrote', dst, i, 'frames')
