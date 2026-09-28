"""Ghost-koi audit: semi-transparent koi (mid saturation orange, lasting 3+ frames) and slow fades.
Reports where ghosts sit (x bands) so seams show up. usage: python3 audit_ghost.py SM.npy [px pw at 640 scale]"""
import sys, cv2, numpy as np
sm=np.load(sys.argv[1]); n=len(sm); H,W=sm[0].shape[:2]
px,pw=(218,202) if W==640 else (0,W)
ghost=np.zeros((n,H,W),bool); solid=np.zeros((n,H,W),bool)
for i,f in enumerate(sm):
    h=cv2.cvtColor(f,cv2.COLOR_BGR2HSV).astype(int); hue=(h[...,0]<24)|(h[...,0]>166)
    solid[i]=hue&(h[...,1]>170)&(h[...,2]>120)
    g=hue&(h[...,1]>55)&(h[...,1]<=150)&(h[...,2]>70)
    # ghost = washed-out orange that is NOT the soft edge of a solid koi
    g&=~(cv2.dilate(solid[i].astype(np.uint8),np.ones((9,9),np.uint8))>0)
    g=cv2.morphologyEx(g.astype(np.uint8),cv2.MORPH_OPEN,np.ones((5,5),np.uint8))>0
    ghost[i]=g
# persistence: ghost pixels present in 3 consecutive frames
pers=ghost&np.roll(ghost,1,0)&np.roll(ghost,-1,0)
area=pers.reshape(n,-1).sum(1)
colprof=pers.sum((0,1))
print('frames with ghost area > 400px (at 640 scale):',int((area>400).sum()),'of',n)
bands=[(0,px-40,'left side'),(px-40,px+40,'LEFT SEAM'),(px+40,px+pw-40,'face'),(px+pw-40,px+pw+40,'RIGHT SEAM'),(px+pw+40,W,'right side')]
tot=colprof.sum()+1e-6
for a,b,nm in bands: print(f'  {nm:11s} x{a}-{b}: {100*colprof[a:b].sum()/tot:.1f}% of ghost pixels, density {colprof[a:b].sum()/max(b-a,1):.1f}/col')
rowprof=pers.sum((0,2)); print('  bottom quarter share: %.1f%%'%(100*rowprof[int(H*0.75):].sum()/tot))
top=np.argsort(area)[-8:][::-1]; print('  worst frames:',[(int(t),int(area[t])) for t in top])
np.save(sys.argv[1].replace('_sm.npy','_ghost_area.npy'),area)
