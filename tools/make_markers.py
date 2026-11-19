"""진여신4(한국판) 목적지 마커 생성기.
사용법: python make_markers.py <원본 romfs 경로> <출력 MapNaviTable.tbb>
원본 romfs/map/all/MapNaviTable.tbb, MapHaichiTable.tbb를 읽어
스토리 이벤트 발동 지점마다 파이널의 빨간 깃발(그림 7110/7111, make_flag.py로 추가) 아이콘 행을 추가한다."""
import sys, struct, re, os
from collections import defaultdict

def read(path):
    d = open(path, 'rb').read(); T = []
    for m in re.finditer(b'TBL1', d):
        o = m.start(); size, rec, _ = struct.unpack_from('<III', d, o + 4)
        n = size // rec
        T.append([rec, [d[o+16+i*rec:o+16+(i+1)*rec] for i in range(n)], d[o+16+n*rec:o+16+size]])
    return d, T

def build(orig, T):
    hs = struct.unpack_from('<I', orig, 4)[0]; body = b''; offs = []
    for rec, rows, tail in T:
        offs.append(len(body)); data = b''.join(rows) + tail
        blk = b'TBL1' + struct.pack('<III', len(data), rec, 0x10) + data
        body += blk + b'\0' * ((-len(blk)) % 16)
    hdr = bytearray(orig[:hs])
    for i, o in enumerate(offs[1:]): struct.pack_into('<I', hdr, 0x10 + 4*i, o)
    return bytes(hdr) + body

MARK, MARK_HI = 7110, 7111   # 파이널 깃발 (make_flag.py로 추가한 그림: 큰 깃발 20x20 / 작은 깃발 10x10)
OX, OZ = -10, -11            # 아이콘 좌표 = 왼쪽 위 기준 보정 (14px "!"에서 맞춘 −7,−8을 20px 깃발 중심에 맞게 −3씩)
ALWAYS_ROOM = 128            # code.ips 패치와 짝: 방 번호 > 63 → 항상 '발견됨' (미탐색 구역에도 표시)
                             # 255(=−1)는 게임이 '특수값'으로 따로 처리해서 숲 같은 맵에서 숨겨짐 → 쓰지 말 것
EVENT_TABLES = (2, 4)        # MapHaichiTable 이벤트 정의 표

def main(romfs, out):
    d, NT = read(os.path.join(romfs, 'map/all/MapNaviTable.tbb'))
    _, MH = read(os.path.join(romfs, 'map/all/MapHaichiTable.tbb'))
    pts, icons, pl, area2pt = {}, defaultdict(list), defaultdict(list), {}
    for r in NT[0][1]:
        m, a, p = struct.unpack_from('<HHH', r, 0); X, Z, W, H = struct.unpack_from('<4h', r, 12)
        pts[(m, p)] = (X, Z, W, H); area2pt.setdefault((m, a), p)
    for r in NT[1][1]:
        icons[(r[0], r[1])].append((r[2], struct.unpack_from('b', r, 3)[0]) + struct.unpack_from('<hh', r, 14))
    for r in MH[0][1]: pl[r[:4]].append(r)
    rows, seen = [], set()
    for ti in EVENT_TABLES:
        for r in MH[ti][1]:
            s, e, _, _ = struct.unpack_from('<HHHH', r, 4)
            name = r[12:28].split(b'\0')[0].decode('latin1')
            if not re.fullmatch(r'e\d{3}_\d{2}', name) or s == 0 or e == 0: continue
            num = int(name[1:4])
            if 500 <= num < 600 or num >= 900: continue   # e5xx: 맵별 잡다한 이벤트(나가기 막기, 대사 등), e9xx: 기타 → 표시 안 함
            for p in pl.get(r[:4], []):
                m, pt = p[8], p[11]; wx, wy, wz = struct.unpack_from('<3h', p, 22)
                if wx == 0 and wy == 0 and abs(wz) <= 100: continue   # 구역 원점 자리표시(들어오면 발동하는 이벤트) → 실제 위치가 아님
                if (m, pt) not in pts:          # 포인트 칸이 0 등 → 구역 번호로 포인트 찾기
                    pt = area2pt.get((m, p[9]), pt)
                if (m, pt) not in pts:          # 포인트가 하나뿐인 맵(도쿄 필드 등)은 그 포인트로
                    only = [q for (mm, q) in pts if mm == m]
                    if len(only) == 1: pt = only[0]
                if (m, pt) not in pts or not icons[(m, pt)]: continue
                X, Z, W, H = pts[(m, pt)]
                if X == Z == W == H == 0:      # 도쿄 필드(맵 101~103): 원래 아이콘도 월드 좌표를 그대로 씀
                    lx, lz = wx, wz
                else:
                    lx = round(X + W + wx * 12 / 512) + OX; lz = round(Z + H + wz * 12 / 512) + OZ
                g, sub, _, _ = min(icons[(m, pt)], key=lambda t: (t[2]-lx)**2 + (t[3]-lz)**2)
                key = (m, pt, s, e, lx // 6, lz // 6)
                if key in seen: continue
                seen.add(key)
                tail = struct.pack('<b', sub) + struct.pack('<HHHHHhh', s, e, 2, MARK, MARK_HI, lx, lz) + b'\0\0'
                rows.append(bytes([m, pt, ALWAYS_ROOM]) + tail)   # 미탐색이어도 보임
    # 같은 지점에서 가까운(12px 이내) 마커들은 한 좌표로 모아 겹쳐 보이게 함
    groups = defaultdict(list)
    for i, r in enumerate(rows): groups[(r[0], r[1])].append(i)
    rows = [bytearray(r) for r in rows]
    for idx in groups.values():
        clusters = []
        for i in idx:
            x, z = struct.unpack_from('<hh', rows[i], 14)
            for c in clusters:
                cx, cz = c[0]
                if abs(cx - x) <= 12 and abs(cz - z) <= 12: c[1].append(i); break
            else: clusters.append([(x, z), [i]])
        for (cx, cz), members in clusters:
            for i in members: struct.pack_into('<hh', rows[i], 14, cx, cz)
    rows = [bytes(r) for r in rows]
    NT[1][1] = NT[1][1] + rows
    open(out, 'wb').write(build(d, NT))
    print(f'markers: {len(rows)} -> {out}')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
