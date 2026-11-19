import numpy as np, struct
def morton():
    t=np.zeros((8,8),int)
    for y in range(8):
        for x in range(8):
            i=0
            for b in range(3): i|=((x>>b)&1)<<(2*b) | ((y>>b)&1)<<(2*b+1)
            t[y,x]=i
    return t
M=morton()
def decode(data,w,h,bpp):
    px=np.frombuffer(data[:w*h*bpp],np.uint8).reshape(-1,bpp)
    img=np.zeros((h,w,bpp),np.uint8); k=0
    for ty in range(h//8):
        for tx in range(w//8):
            img[ty*8:ty*8+8,tx*8:tx*8+8]=px[k:k+64][M]; k+=64
    return img
def encode(img):
    h,w,bpp=img.shape; out=[]
    inv=np.argsort(M.ravel())
    for ty in range(h//8):
        for tx in range(w//8):
            tile=img[ty*8:ty*8+8,tx*8:tx*8+8].reshape(64,bpp)
            out.append(tile[inv])
    return np.concatenate(out).tobytes()
