"""Audit a loop for koi popping in/out: per grid cell, orange area that changes abruptly in 1-2 frames."""
import sys, cv2, numpy as np
src, tag = sys.argv[1], sys.argv[2]
c=cv2.VideoCapture(src); sm=[]
while True:
    ok,f=c.read()
    if not ok: break
    sm.append(cv2.resize(f,(640,int(640*f.shape[0]/f.shape[1])) if f.shape[1]>=f.shape[0] else (360,640),interpolation=cv2.INTER_AREA))
n=len(sm); H,W=sm[0].shape[:2]
np.save(f'audit/{tag}_sm.npy',np.array(sm))
def om(f):
    h=cv2.cvtColor(f,cv2.COLOR_BGR2HSV); return ((((h[...,0]<22)|(h[...,0]>168))&(h[...,1]>140)&(h[...,2]>110))).astype(np.float32)
O=np.array([om(f) for f in sm])
g=40
cells=O.reshape(n,H//g,g,W//g,g).mean((2,4)) if H%g==0 and W%g==0 else None
if cells is None:
    Hc,Wc=H//g*g,W//g*g; cells=O[:,:Hc,:Wc].reshape(n,Hc//g,g,Wc//g,g).mean((2,4))
d1=np.abs(np.roll(cells,-1,0)-cells)            # change i -> i+1
# motion-consistent change is spread over neighbours; a pop is a big change in one step vs small steps around it
prev=np.abs(cells-np.roll(cells,1,0)); nxt2=np.abs(np.roll(cells,-2,0)-np.roll(cells,-1,0))
score=d1-0.5*(prev+nxt2)
ev=[]
for i in range(n):
    s=score[i]; k=np.argwhere(s>0.28)
    if len(k): ev.append((i,len(k),round(float(s.max()),2)))
print(tag,'frames',n,'pop candidates (frame->frame+1, cells, peak):',ev)
