"""진여신4(한국판) 목적지 마커 생성기.
사용법: python make_markers.py <원본 romfs 경로> <출력 MapNaviTable.tbb>
원본 romfs/map/all/MapNaviTable.tbb, MapHaichiTable.tbb를 읽어
스토리 이벤트 발동 지점마다 빨간 "!"(그림 7014) 아이콘 행을 추가한다."""
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
# 메인 퀘스트가 둘 겹칠 때 순서 맞추기: (이벤트, 원래 시작, 원래 종료) → 새 시작·종료
#   e080_01 악마토벌대 기지(남서쪽 도시, 퀘스트 「악마토벌대의 기지를 찾아라」): 원래 110부터 보이지만
#   110은 우에노 퀘스트 「피알레이 퇴치」 전에 켜짐 → 피알레이 퇴치 완료(108) 뒤부터 표시
#   그 사이 피알레이 퇴치 뒤 필드 다리 이벤트(e079_01, 108→1539)를 먼저 보여 주고, 그 이벤트를 본 뒤(1539)부터 기지 표시
WINDOW_OVERRIDE = {('e080_01', 110, 111): (1539, 111)}
ROUTE_FLAGS = False          # 도시 안 구역 사이 문 '길 안내' 깃발 (사용자 선택으로 끔, 도쿄 필드 입구 깃발은 유지)

def main(romfs, out, events_dir=None):
    import questinfo
    QP = questinfo.load(events_dir or os.path.join(romfs, 'event'))
    QW = questinfo.windows(QP)
    FAM, ALLF = questinfo.story_sets(QP)
    import bisect
    mainkeys = set()   # (지도, 시작, 종료) — 메인 퀘스트 이벤트
    d, NT = read(os.path.join(romfs, 'map/all/MapNaviTable.tbb'))
    _, MH = read(os.path.join(romfs, 'map/all/MapHaichiTable.tbb'))
    pts, icons, pl, area2pt = {}, defaultdict(list), defaultdict(list), {}
    for r in NT[0][1]:
        m, a, p = struct.unpack_from('<HHH', r, 0); X, Z, W, H = struct.unpack_from('<4h', r, 12)
        pts[(m, p)] = (X, Z, W, H); area2pt.setdefault((m, a), p)
    for r in NT[1][1]:
        icons[(r[0], r[1])].append((r[2], struct.unpack_from('b', r, 3)[0]) + struct.unpack_from('<hh', r, 14))
    for r in MH[0][1]: pl[r[:4]].append(r)
    links = defaultdict(list)   # (지도, 들어가는 구역) → 같은 지도 다른 구역에 있는 연결 배치
    for r in MH[0][1]:
        if r[8] <= 100 and r[18] == r[8] and r[19] != r[9] and r[19]: links[(r[8], r[19])].append(r)
    rows, seen = [], set()
    jobs = []
    for ti in EVENT_TABLES:
        for r in MH[ti][1]:
            s, e, _, _ = struct.unpack_from('<HHHH', r, 4)
            jobs.append((r, s, e, r[12:28].split(b'\0')[0].decode('latin1'), False))
    # 메인 퀘스트를 NPC에게 말을 걸어 받는 경우(예: 헌터 상회 안 '백안의 남자' → 피알레이 퇴치):
    #   수락 스크립트(97)는 지도에 위치가 없음 → 같은 이벤트 묶음의 배치 이벤트(예: e076_02 헌터 상회 입구) 자리에
    #   '그 이벤트를 본 뒤 ~ 퀘스트 받기 전' 동안 깃발을 계속 표시 (시작 = 그 이벤트의 종료 플래그, 종료 = 수락이 켜는 플래그)
    placed = {j[3] for j in jobs}
    for pname, cs in QP.items():
        if pname in placed or not any(c == 97 and a and 0 < a[-1] < 100 for c, a in cs): continue
        acc = [a[-1] for c, a in cs if c == 1 and a and 0 < a[-1] < 1000]
        if not acc: continue
        fa = min(acc)
        for (r, s, e, name, _) in list(jobs):
            if name[:4] == pname[:4] and 0 < e < 1000 and fa not in (s, e):
                jobs.append((r, e, fa, name, True))
    for (r, s, e, name, forced) in jobs:
            ovr = WINDOW_OVERRIDE.get((name, s, e))
            if not re.fullmatch(r'e\d{3}_\d{2}', name) or s == 0 or e == 0: continue
            num = int(name[1:4])
            if 500 <= num < 600 or num >= 900: continue   # e5xx: 맵별 잡다한 이벤트(나가기 막기, 대사 등), e9xx: 기타 → 표시 안 함
            # 메인 퀘스트 진행 이벤트인지: 종료 플래그가 어느 메인 퀘스트 구간 안에 있으면 메인
            tq = questinfo.tightest(QW, e) if e < 1000 else None
            is_main = forced or (tq is not None and s <= tq[2])
            if ovr: s, e = ovr                     # 메인 여부는 원래 구간으로 판단한 뒤 표시 구간만 바꿈
            if e >= 1000 and FAM.get(name[:4]):
                # '처음 방문' 형식(종료 플래그 1500번대 등) 이벤트라도 이야기 플래그를 켜면 진행 이벤트
                #   예: e073 우에노 헌터 상회 첫 방문 → 102를 켬. 102 바로 앞 이야기 플래그(100)가 켜진 뒤부터 표시
                f = min(FAM[name[:4]])
                k = bisect.bisect_left(ALLF, f)
                if questinfo.tightest(QW, f) and k > 0 and f - ALLF[k-1] <= 5 and f - s > 5:   # 시작 플래그가 이미 바로 앞 단계면(e079_01 108→110) 그대로 둠
                    is_main = True; s = max(s, ALLF[k-1]); tq = None
            for p in pl.get(r[:4], []):
                m, wx, wy, wz = p[8], *struct.unpack_from('<3h', p, 22)
                if wx == 0 and wy == 0 and abs(wz) <= 100: continue   # 구역 원점 자리표시(들어오면 발동하는 이벤트) → 실제 위치가 아님
                spots = [(p[9], p[11], wx, wz)]
                # 메인 퀘스트 목적지가 다른 구역(예: 우에노 지하)에 있으면, 그 구역으로 들어가는 입구에도 깃발 (2단계까지)
                if ROUTE_FLAGS and is_main and m <= 100:
                    seen_a, front, route = {p[9]}, [p[9]], []
                    for _ in range(2):
                        nxt, step = [], []
                        for a in front:
                            for q in links.get((m, a), ()):
                                if q[9] == p[9]: continue      # 목적지 구역 안의 출구는 제외
                                qx, _, qz = struct.unpack_from('<3h', q, 22)
                                step.append((q[9], area2pt.get((m, q[9]), 0), qx, qz))   # 연결 배치의 포인트 칸은 '도착' 구역 것이라 출발 구역으로 다시 찾음
                                if q[9] not in seen_a: seen_a.add(q[9]); nxt.append(q[9])
                        if len(route) + len(step) > 6: break   # 길이 너무 많이 갈라지는 던전은 생략
                        route += step; front = nxt
                    spots += route
                for area, pt, x0, z0 in spots:
                    if (m, pt) not in pts:          # 포인트 칸이 0 등 → 구역 번호로 포인트 찾기
                        pt = area2pt.get((m, area), pt)
                    if (m, pt) not in pts:          # 포인트가 하나뿐인 맵(도쿄 필드 등)은 그 포인트로
                        only = [q for (mm, q) in pts if mm == m]
                        if len(only) == 1: pt = only[0]
                    if (m, pt) not in pts or not icons[(m, pt)]: continue
                    X, Z, W, H = pts[(m, pt)]
                    if X == Z == W == H == 0:      # 도쿄 필드(맵 101~103): 원래 아이콘도 월드 좌표를 그대로 씀
                        lx, lz = x0, z0
                    else:
                        lx = round(X + W + x0 * 12 / 512) + OX; lz = round(Z + H + z0 * 12 / 512) + OZ
                    g, sub, _, _ = min(icons[(m, pt)], key=lambda t: (t[2]-lx)**2 + (t[3]-lz)**2)
                    key = (m, pt, s, e, lx // 6, lz // 6)
                    if key in seen: continue
                    seen.add(key)
                    tail = struct.pack('<b', sub) + struct.pack('<HHHHHhh', s, e, 2, MARK, MARK_HI, lx, lz) + b'\0\0'
                    rows.append(bytes([m, pt, ALWAYS_ROOM]) + tail)   # 미탐색이어도 보임
                    if is_main: mainkeys.add((m, s, e))
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
    # 도쿄 필드(맵 101~103): 도시·던전 안에 진행 가능한 이벤트가 있으면 필드의 그 입구에도 깃발
    #   입구 배치(MapHaichiTable 표0): b8 필드 맵, b16 필드 아이콘 번호, b18 들어가는 지도 번호(MapNavi 맵)
    by_map = defaultdict(set)
    for r in rows:
        if r[0] <= 100:
            st, en = struct.unpack_from('<HH', r, 4)
            # 필드 입구에는 이야기 진행 이벤트만: 시작~종료 플래그 간격이 좁은 것(1~20).
            # 간격이 넓은 것(예: 96 → 1591 '처음 방문' 연출, 211 → 1625 등)은 언제든 볼 수 있는 곁가지라 필드에선 뺌
            # + 메인 퀘스트 이벤트만 (서브·챌린지 이벤트는 도시 안 지도에만 표시)
            if (r[0], st, en) in mainkeys and (0 < abs(en - st) <= 20 or en >= 1000 or st >= 1000): by_map[r[0]].add((st, en))
    field_pt = {m: q for (m, q) in pts if m > 100}
    # 필드에서 바로 못 들어가는 지도(예: 도시 안의 지하)는 그 지도로 이어지는 바깥 지도의 이벤트로 취급
    #   연결: 배치 b8 = 있는 지도, b18 = 이어지는 지도 (필드로 나가는 연결은 제외)
    navimaps = {m for (m, q) in pts}
    direct = {p[18] for p in MH[0][1] if p[8] in field_pt and p[18] and p[16]}
    parents = defaultdict(set)
    for p in MH[0][1]:
        if p[8] <= 100 and p[18] in navimaps and p[18] <= 100 and p[18] != p[8]:
            parents[p[18]].add(p[8])
    inner = {m: set(v) for m, v in by_map.items()}
    for child in sorted(navimaps - direct):
        if child > 100 or child in (0, 10, 13) or child not in inner: continue   # 미카도국·나락·키치죠지 숲(동쪽 세계)은 도쿄 입구와 무관
        for par in parents[child]:              # 한 단계 바깥 지도만 (너무 넓게 퍼지지 않게)
            if par in direct: by_map[par] |= inner[child]
    extra, seen_e = [], set()
    for p in MH[0][1]:
        m, dest = p[8], p[18]
        if m not in field_pt or not dest or not p[16] or dest not in by_map: continue
        wx, wy, wz = struct.unpack_from('<3h', p, 22)
        for s, e in sorted(by_map[dest]):
            k = (m, wx, wz, s, e)
            if k in seen_e: continue
            seen_e.add(k)
            extra.append(bytes([m, field_pt[m], ALWAYS_ROOM]) + struct.pack('<b', 0) +
                         struct.pack('<HHHHHhh', s, e, 2, MARK, MARK_HI, wx, wz) + b'\0\0')
    print(f'field entrance flags: {len(extra)}')
    rows += extra
    NT[1][1] = NT[1][1] + rows
    open(out, 'wb').write(build(d, NT))
    print(f'markers: {len(rows)} -> {out}')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
