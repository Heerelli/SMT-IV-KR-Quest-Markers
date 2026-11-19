"""진여신4 한국판에 파이널의 목적지 깃발 아이콘을 추가한다.
- tex/stex/icon/automap_icon3.stex : LA8 → RGBA4로 바꾸고 빈 자리에 파이널 깃발 그림(큰 것 20x20, 작은 것 10x10) 복사
- tex/icon.ttd : automap_icon3 그룹 끝에 깃발 그림 2개(7110 큰 깃발, 7111 작은 깃발)와 색 정보 2개 추가
사용법: python make_flag.py <진여신4 romfs> <파이널 romfs> <출력 romfs>"""
import struct, sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import la

FLAG_A = [(122, (66, 79, 20, 20)), (124, (0, 98, 10, 10))]   # 파이널 그림 번호 7122, 7124
GROUP = 7                                                    # automap_icon3

def rgba4(img):
    v = ((img[..., 0].astype(np.uint16) >> 4) << 12) | ((img[..., 1].astype(np.uint16) >> 4) << 8) | \
        ((img[..., 2].astype(np.uint16) >> 4) << 4) | (img[..., 3].astype(np.uint16) >> 4)
    b = np.stack([v & 255, v >> 8], -1).astype(np.uint8)
    return la.encode(b)

def dec_rgba4(data, w, h):
    raw = la.decode(data, w, h, 2); v = raw[..., 0].astype(int) | (raw[..., 1].astype(int) << 8)
    return (np.stack([(v >> 12) & 15, (v >> 8) & 15, (v >> 4) & 15, v & 15], -1) * 17).astype(np.uint8)

def tex(s4, s4a, out):
    d = open(s4, 'rb').read(); da = open(s4a, 'rb').read()
    w, h = struct.unpack_from('<II', d, 0xC)
    assert struct.unpack_from('<H', d, 0x18)[0] == 0x6758
    raw = la.decode(d[0x80:], w, h, 2)                 # [A, L]
    img = np.stack([raw[..., 1]] * 3 + [raw[..., 0]], -1)
    fa = dec_rgba4(da[0x80:], w, h)
    for _, (u, v, cw, ch) in FLAG_A:
        img[v:v+ch, u:u+cw] = fa[v:v+ch, u:u+cw]
    hdr = bytearray(d[:0x80]); struct.pack_into('<H', hdr, 0x14, 0x8033); struct.pack_into('<H', hdr, 0x18, 0x6752)
    open(out, 'wb').write(bytes(hdr) + rgba4(img))

def ttd(t4, t4a, out):
    d = open(t4, 'rb').read(); da = open(t4a, 'rb').read()
    oa, na, ob, nb, oc, nc, os_ = struct.unpack_from('<7I', d, 0x14)
    oaa, naa, oba, nba, oca, nca, osa = struct.unpack_from('<7I', da, 0x14)
    A = [d[oa+i*80:oa+(i+1)*80] for i in range(na)]
    B = [bytearray(d[ob+i*20:ob+(i+1)*20]) for i in range(nb)]
    C = [list(struct.unpack_from('<4I', d, oc+i*16)) for i in range(nc)]
    Ca = [struct.unpack_from('<4I', da, oca+i*16) for i in range(nca)]
    assert GROUP == nc - 1 and C[GROUP][0] + C[GROUP][3] == nb   # 마지막 그룹이라 끝에 붙이면 됨
    new_ids = []
    for loc, _ in FLAG_A:
        rb = bytearray(da[oba+(Ca[GROUP][0]+loc)*20: oba+(Ca[GROUP][0]+loc+1)*20])
        ai = struct.unpack_from('<H', rb, 12)[0]
        _, (_, _, cw, ch) = [f for f in FLAG_A if f[0] == loc][0]
        a = bytearray(A[81])                              # 진여신4의 흰색(색 입히지 않음) 스타일을 바탕으로
        struct.pack_into('<HH', a, 0, cw, ch)             # 그림 크기만 깃발에 맞춤 → 파이널 그림 색 그대로
        A.append(bytes(a))
        struct.pack_into('<H', rb, 12, len(A) - 1)       # 새 색 정보 번호
        new_ids.append(7000 + C[GROUP][3]); B.append(rb); C[GROUP][3] += 1
    body = b''.join(A); nob = 0x30 + len(body); body += b''.join(B)
    noc = 0x30 + len(body); body += b''.join(struct.pack('<4I', *c) for c in C)
    nos = 0x30 + len(body); body += d[os_:]
    hdr = bytearray(d[:0x30]); struct.pack_into('<7I', hdr, 0x14, 0x30, len(A), nob, len(B), noc, len(C), nos)
    open(out, 'wb').write(bytes(hdr) + body)
    return new_ids

if __name__ == '__main__':
    r4, r4a, o = sys.argv[1:4]
    os.makedirs(os.path.join(o, 'tex/stex/icon'), exist_ok=True)
    tex(os.path.join(r4, 'tex/stex/icon/automap_icon3.stex'), os.path.join(r4a, 'tex/stex/icon/automap_icon3.stex'), os.path.join(o, 'tex/stex/icon/automap_icon3.stex'))
    print('new sprite ids:', ttd(os.path.join(r4, 'tex/icon.ttd'), os.path.join(r4a, 'tex/icon.ttd'), os.path.join(o, 'tex/icon.ttd')))
