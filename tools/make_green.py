"""make_flag.py로 만든 깃발(7110 큰 것, 7111 작은 것)을 초록색으로 복사해 7112, 7113으로 추가한다 (챌린지 퀘스트용).
사용법: python make_green.py <make_flag 출력 romfs>  (icon.ttd, automap_icon3.stex를 그 자리에서 고침)"""
import struct, sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_flag import rgba4, dec_rgba4
GROUP = 7

def green(px):
    """빨강 → 초록: 색 있는 픽셀만 빨강/초록 채널을 맞바꿈 (흰 깃대·검은 테두리는 그대로)"""
    out = px.copy(); out[..., 0], out[..., 1] = px[..., 1], px[..., 0]; return out

def main(root):
    tp = os.path.join(root, 'tex/icon.ttd'); sp = os.path.join(root, 'tex/stex/icon/automap_icon3.stex')
    t = open(tp, 'rb').read(); s = open(sp, 'rb').read()
    oa, na, ob, nb, oc, nc, os_ = struct.unpack_from('<7I', t, 0x14)
    A = [t[oa+i*80:oa+(i+1)*80] for i in range(na)]
    B = [bytearray(t[ob+i*20:ob+(i+1)*20]) for i in range(nb)]
    C = [list(struct.unpack_from('<4I', t, oc+i*16)) for i in range(nc)]
    assert GROUP == nc - 1 and C[GROUP][0] + C[GROUP][3] == nb
    if C[GROUP][3] >= 114: print('already has green flags'); return
    w, h = struct.unpack_from('<II', s, 0xC); img = dec_rgba4(s[0x80:], w, h)
    occ = img[..., 3] > 0
    for i in range(C[GROUP][0], nb):
        u, v, cw, ch = struct.unpack_from('<4H', B[i], 0); occ[v:v+ch, u:u+cw] = True
    ids = []
    for sid in (110, 111):                      # 7110, 7111
        src = B[C[GROUP][0] + sid]; u, v, cw, ch = struct.unpack_from('<4H', src, 0)
        spot = next((x, y) for y in range(0, h-ch+1, 2) for x in range(0, w-cw+1, 2) if not occ[y:y+ch+1, x:x+cw+1].any())
        x, y = spot; img[y:y+ch, x:x+cw] = green(img[v:v+ch, u:u+cw]); occ[y:y+ch+1, x:x+cw+1] = True
        nbr = bytearray(src); struct.pack_into('<HH', nbr, 0, x, y)
        B.append(nbr); ids.append(7000 + C[GROUP][3]); C[GROUP][3] += 1
    body = b''.join(A); nob = 0x30 + len(body); body += b''.join(B)
    noc = 0x30 + len(body); body += b''.join(struct.pack('<4I', *c) for c in C)
    nos = 0x30 + len(body); body += t[os_:]
    hdr = bytearray(t[:0x30]); struct.pack_into('<7I', hdr, 0x14, 0x30, len(A), nob, len(B), noc, len(C), nos)
    open(tp, 'wb').write(bytes(hdr) + body)
    open(sp, 'wb').write(s[:0x80] + rgba4(img))
    print('green sprite ids:', ids)

if __name__ == '__main__': main(sys.argv[1])
