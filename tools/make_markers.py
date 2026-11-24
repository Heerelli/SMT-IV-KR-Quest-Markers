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
GREEN, GREEN_HI = 7112, 7113 # 초록 깃발 (make_green.py) — 챌린지 퀘스트(e6xx·e7xx) 목적지
OX, OZ = -10, -11            # 아이콘 좌표 = 왼쪽 위 기준 보정 (14px "!"에서 맞춘 −7,−8을 20px 깃발 중심에 맞게 −3씩)
ALWAYS_ROOM = 128            # code.ips 패치와 짝: 방 번호 > 63 → 항상 '발견됨' (미탐색 구역에도 표시)
                             # 255(=−1)는 게임이 '특수값'으로 따로 처리해서 숲 같은 맵에서 숨겨짐 → 쓰지 말 것
EVENT_TABLES = (2, 4)        # MapHaichiTable 이벤트 정의 표
# 메인 퀘스트가 둘 겹칠 때 순서 맞추기: (이벤트, 원래 시작, 원래 종료) → 새 시작·종료
#   e080_01 악마토벌대 기지(남서쪽 도시, 퀘스트 「악마토벌대의 기지를 찾아라」): 원래 110부터 보이지만
#   110은 우에노 퀘스트 「피알레이 퇴치」 전에 켜짐 → 피알레이 퇴치 완료(108) 뒤부터 표시
#   그 사이 피알레이 퇴치 뒤 필드 다리 이벤트(e079_01, 108→1539)를 먼저 보여 주고, 그 이벤트를 본 뒤(1539)부터 기지 표시
#   e114_01 이케부쿠로 화염벽(토지신의 지령의 부적으로 여는 결계): 부적은 메인 퀘스트 「도청의 악마를 퇴치」 완료(138) 보상
#   → 부적을 얻기 전에는 표시하지 않음 (원래 96부터 열려 있음)
WINDOW_OVERRIDE = {('e080_01', 110, 111): (1539, 111),
                   ('e114_01', 96, 1594): (138, 1594),
                   # e094_04 신주쿠(아수라회 쪽) 이벤트: 「도청의 악마를 퇴치」 수락(122)까지만 표시하고 메인으로 취급
                   ('e094_04', 119, 1610): (119, 122),
                   # e098_01 도청: 「도청의 악마를 퇴치」를 받은 뒤(122)부터 (그 전엔 셔터 앞 남자 깃발만)
                   ('e098_01', 121, 1610): (122, 1610)}
FORCE_MAIN = {'e094_04', 'e098_01'}
# 메인 퀘스트와 이어지는 챌린지 이벤트 → 빨간 깃발 (e710: 신주쿠 셔터 앞 사람, 「콥스들을 죽여라」를 깨야 메인 진행)
MAIN_LINKED = {'e710'}
# 같은 배치 자리에 표시 구간을 하나 더 추가: 이벤트 이름 → [(시작, 종료)]
#   e710 신주쿠 셔터 앞 남자: 「콥스들을 죽여라」를 끝낸 뒤(121) 다시 말을 걸어 「도청의 악마를 퇴치」를 받을 때(122)까지
EXTRA_WINDOWS = {}
# MapNpcTable에 위치가 있는 이벤트 NPC (이름 → 표시 구간). 셔터 앞 남자 = e094_03 (신주쿠 11구역, 「도청의 악마를 퇴치」 수락)
#   e710_02/05 배치 자리는 남자 위치가 아니라(동쪽 출입구 길 등) 쓰지 않음 → 「콥스들을 죽여라」 전후 모두 이 남자 위치에 표시
NPC_EVENTS = {'e094_03': (0, 122)}
SKIP_EVENTS = {'e710_02', 'e710_04', 'e710_05'}
# 이벤트가 자동 지도 없는 실내 맵에 있을 때, 그 실내로 들어가는 문(배치 키)에도 표시: 이벤트 → [(배치 키, 표시할 포인트)]
#   e112_01 (「세이오보를 사냥하라」, 맵 24 실내) ← 이케부쿠로 선죠인 앞(맵 4 구역 1) 문 배치 03104000 (type 29, 포인트 칸이 크기 0이라 구역 1 포인트 38로)
DOOR_SPOTS = {'e112_01': [(bytes.fromhex('03104000'), 38, 450, -200)]}   # (키, 포인트, 문 너머로 옮길 x, z — 화면상 동쪽)
# 위치가 없는 메인 이벤트용 필드 입구 깃발: (목적지 지도, 시작, 종료) — e094_04 → 신주쿠(지도 1), 퀘스트 받을 때까지
EXTRA_FIELD = [(1, 119, 122)]
FLOOR_COPY = False           # 여러 층 구역의 다른 층에도 복사 — v36에서 세이브 불러올 때 앱이 꺼져서 끔
ROUTE_FLAGS = False          # 도시 안 구역 사이 문 '길 안내' 깃발 (사용자 선택으로 끔, 도쿄 필드 입구 깃발은 유지)

def main(romfs, out, events_dir=None):
    import questinfo
    QP = questinfo.load(events_dir or os.path.join(romfs, 'event'))
    QW = questinfo.windows(QP)
    FAM, ALLF = questinfo.story_sets(QP)
    import bisect
    mainkeys = set()   # (지도, 시작, 종료) — 메인 퀘스트 이벤트
    chalkeys = set()   # (지도, 시작, 종료) — 챌린지 퀘스트 이벤트
    d, NT = read(os.path.join(romfs, 'map/all/MapNaviTable.tbb'))
    _, MH = read(os.path.join(romfs, 'map/all/MapHaichiTable.tbb'))
    pts, icons, pl, area2pt = {}, defaultdict(list), defaultdict(list), {}
    pt_area = {}
    for r in NT[0][1]:
        m, a, p = struct.unpack_from('<HHH', r, 0); X, Z, W, H = struct.unpack_from('<4h', r, 12)
        pts[(m, p)] = (X, Z, W, H); area2pt.setdefault((m, a), p); pt_area[(m, p)] = a
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
    for (r, s, e, name, _) in list(jobs):
        for s2, e2 in EXTRA_WINDOWS.get(name, []):
            jobs.append((r, s2, e2, name, False))
    jobs = [j for j in jobs if j[3] not in SKIP_EVENTS]
    _, NPC = read(os.path.join(romfs, 'map/all/MapNpcTable.tbb'))
    for nr in NPC[0][1]:
        nname = nr[8:40].split(b'\0')[0].decode('latin1')
        if nname not in NPC_EVENTS: continue
        nm_, na_ = struct.unpack_from('<HH', nr, 0); nx, ny, nz = struct.unpack_from('<3h', nr, 42)
        key = b'NPC' + bytes([len(jobs) & 0xFF])                  # 가짜 키 → 가짜 배치 한 줄
        fake = bytearray(32); fake[:4] = key; fake[8] = nm_; fake[9] = na_; struct.pack_into('<3h', fake, 22, nx, ny, nz)
        pl[bytes(key)].append(bytes(fake))
        fr = bytearray(28); fr[:4] = key
        s_, e_ = NPC_EVENTS[nname]; jobs.append((bytes(fr), s_, e_, nname, False))
        FORCE_MAIN.add(nname)
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
            if not re.fullmatch(r'e\d{3}_\d{2}', name) or e == 0: continue
            num = int(name[1:4])
            # 시작 플래그 0 = 조건 없이 항상 열려 있는 이벤트 → 보통은 제외.
            #   단 챌린지(e6xx·e7xx)는 퀘스트를 주는/진행시키는 NPC 대화인 경우가 있어 표시 (예: e710_02 신주쿠 셔터 앞 사람 → 「콥스들을 죽여라」)
            if s == 0 and not 600 <= num < 800 and name not in NPC_EVENTS: continue
            if 500 <= num < 600 or num >= 900: continue   # e5xx: 맵별 잡다한 이벤트(나가기 막기, 대사 등), e9xx: 기타 → 표시 안 함
            # 메인 퀘스트 진행 이벤트인지: 종료 플래그가 어느 메인 퀘스트 구간 안에 있으면 메인
            tq = questinfo.tightest(QW, e) if e < 1000 else None
            is_main = forced or name in FORCE_MAIN or (tq is not None and s <= tq[2])
            is_chal = 600 <= num < 800 and name[:4] not in MAIN_LINKED   # e6xx·e7xx = 챌린지 퀘스트 이벤트 → 초록 깃발
            if is_chal: is_main = False
            spr, spr_hi = (GREEN, GREEN_HI) if is_chal else (MARK, MARK_HI)
            if e >= 1000 and FAM.get(name[:4]):
                # '처음 방문' 형식(종료 플래그 1500번대 등) 이벤트라도 이야기 플래그를 켜면 진행 이벤트
                #   예: e073 우에노 헌터 상회 첫 방문 → 102를 켬. 102 바로 앞 이야기 플래그(100)가 켜진 뒤부터 표시
                f = min(FAM[name[:4]])
                k = bisect.bisect_left(ALLF, f)
                if questinfo.tightest(QW, f) and k > 0 and f - ALLF[k-1] <= 5 and f - s > 5:   # 시작 플래그가 이미 바로 앞 단계면(e079_01 108→110) 그대로 둠
                    is_main = True; s = max(s, ALLF[k-1]); tq = None
            if ovr: s, e = ovr                     # 메인 여부는 원래 구간으로 판단한 뒤 표시 구간만 바꿈 (가장 마지막에 적용)
            plist = pl.get(r[:4], [])   # 키 첫 바이트 0x80 이벤트(e094_04 등)는 위치 없음 — 하위 비트로 찾으면 유물(type 24) 자리가 나와 틀림
            for dk, dpt, ddx, ddz in DOOR_SPOTS.get(name, []):
                for dp in pl.get(dk, []):
                    dp = bytearray(dp); dp[11] = dpt
                    x_, y_, z_ = struct.unpack_from('<3h', dp, 22); struct.pack_into('<3h', dp, 22, x_ + ddx, y_, z_ + ddz)
                    plist = list(plist) + [bytes(dp)]
            for p in plist:
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
                # 층이 여러 개인 구역(예: 신주쿠 도청 — 같은 구역에 지도 범위가 같은 포인트 1·2·3·170)은
                #   지도가 지금 층의 포인트만 그리므로, 메인 목적지는 같은 구역의 다른 층 포인트에도 표시
                if FLOOR_COPY and is_main and m <= 100:
                    more = []
                    for area, pt, x0, z0 in spots:
                        rp = pt if (m, pt) in pts else area2pt.get((m, area), pt)
                        if (m, rp) not in pts: continue
                        more += [(area, q, x0, z0) for (mm, q), rect in pts.items()
                                 if mm == m and q != rp and rect == pts[(m, rp)] and pt_area.get((m, q)) == pt_area.get((m, rp))]
                    spots = spots + more
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
                    tail = struct.pack('<b', sub) + struct.pack('<HHHHHhh', s, e, 2, spr, spr_hi, lx, lz) + b'\0\0'
                    rows.append(bytes([m, pt, ALWAYS_ROOM]) + tail)   # 미탐색이어도 보임
                    if is_main: mainkeys.add((m, s, e))
                    if is_chal: chalkeys.add((m, s, e))
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
            st, en = struct.unpack_from('<HH', r, 4); spr = struct.unpack_from('<H', r, 10)[0]
            # 필드 입구에는 이야기 진행 이벤트만: 시작~종료 플래그 간격이 좁은 것(1~20).
            # 간격이 넓은 것(예: 96 → 1591 '처음 방문' 연출, 211 → 1625 등)은 언제든 볼 수 있는 곁가지라 필드에선 뺌
            # + 메인 퀘스트 이벤트만 (서브·챌린지 이벤트는 도시 안 지도에만 표시)
            key = (r[0], st, en)
            if (key in mainkeys or (spr == GREEN and key in chalkeys)) and (0 < abs(en - st) <= 20 or en >= 1000 or st >= 1000):
                by_map[r[0]].add((st, en, spr))
    for dm, st, en in EXTRA_FIELD: by_map[dm].add((st, en, MARK))
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
        for s, e, spr in sorted(by_map[dest]):
            k = (m, wx, wz, s, e, spr)
            if k in seen_e: continue
            seen_e.add(k)
            extra.append(bytes([m, field_pt[m], ALWAYS_ROOM]) + struct.pack('<b', 0) +
                         struct.pack('<HHHHHhh', s, e, 2, spr, spr + 1, wx, wz) + b'\0\0')
    print(f'field entrance flags: {len(extra)}')
    rows += extra
    NT[1][1] = NT[1][1] + rows
    open(out, 'wb').write(build(d, NT))
    print(f'markers: {len(rows)} -> {out}')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
