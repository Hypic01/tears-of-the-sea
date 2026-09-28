"""Encode a master loop for the web: AV1 (primary) + H.264 (fallback), each under a size cap.

usage: python3 web_encode.py MASTER.mp4 OUT_PREFIX [max_mb=14]
writes OUT_PREFIX.av1.mp4 and OUT_PREFIX.h264.mp4
env: CODECS=av1,h264 (default both), H264_SCALE=WxH to downscale only the H.264 fallback
"""
import sys, subprocess, os

src, prefix = sys.argv[1], sys.argv[2]
cap_mb = float(sys.argv[3]) if len(sys.argv) > 3 else 14.0
codecs = os.environ.get('CODECS', 'av1,h264').split(',')
h264_vf = ['-vf', 'scale=' + os.environ['H264_SCALE'].replace('x', ':') + ':flags=lanczos'] if os.environ.get('H264_SCALE') else []


def enc(args, out):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', src, *args, '-pix_fmt', 'yuv420p', '-an', '-movflags', '+faststart', out], check=True)
    return os.path.getsize(out) / 1e6


for crf in (28, 30, 32, 34, 36, 38, 40) if 'av1' in codecs else ():
    mb = enc(['-c:v', 'libsvtav1', '-preset', '5', '-crf', str(crf), '-g', '240', '-svtav1-params', 'tune=0'], prefix + '.av1.mp4')
    print(f'av1  crf {crf}: {mb:.1f} MB')
    if mb <= cap_mb:
        break
for crf in (20, 21, 22, 23, 24, 25, 26, 27, 28) if 'h264' in codecs else ():
    mb = enc([*h264_vf, '-c:v', 'libx264', '-preset', 'slow', '-crf', str(crf), '-profile:v', 'high'], prefix + '.h264.mp4')
    print(f'h264 crf {crf}: {mb:.1f} MB')
    if mb <= cap_mb:
        break
