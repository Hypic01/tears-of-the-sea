import sys, cv2, numpy as np
sm=np.load(sys.argv[1]); n=len(sm); H,W=sm[0].shape[:2]
def blobs(f):
    h=cv2.cvtColor(f,cv2.COLOR_BGR2HSV); m=((((h[...,0]<22)|(h[...,0]>168))&(h[...,1]>140)&(h[...,2]>110))).astype(np.uint8)
    m=cv2.morphologyEx(m,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
    nl,lab,st,_=cv2.connectedComponentsWithStats(m)
    return lab,[k for k in range(1,nl) if st[k,4]>120],st
L=[blobs(f) for f in sm]; ev=[]
for i in range(n):
    lab,ks,st=L[i]; plab,pks,pst=L[i-1]
    pm=cv2.dilate((plab>0).astype(np.uint8),np.ones((15,15),np.uint8)); nm=cv2.dilate((lab>0).astype(np.uint8),np.ones((15,15),np.uint8))
    for k in ks:
        x,y,w,h,a=st[k]
        if (pm[lab==k]>0).mean()<0.05 and x>6 and y>6 and x+w<W-6 and y+h<H-6: ev.append(('born',i,(int(x),int(y),int(w),int(h)),int(a)))
    for k in pks:
        x,y,w,h,a=pst[k]
        if (nm[plab==k]>0).mean()<0.05 and x>6 and y>6 and x+w<W-6 and y+h<H-6: ev.append(('died',i,(int(x),int(y),int(w),int(h)),int(a)))
print('born/died away from edges:',ev)
