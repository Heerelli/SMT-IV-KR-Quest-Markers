"""진여신4(한국판) 미카도국 장소 이름에 이벤트 표시를 붙인다.
메인 이벤트 → "이름 ！", 지금만 볼 수 있는 이벤트 → "이름 ＊", 중요하지 않은 이벤트(e501_xx 마을 대사 등) → 표시 안 함.
사용법: python make_mikado.py <원본 MikadoTable.tbb> <출력 MikadoTable.tbb>"""
import sys, struct, re
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from make_markers import read, build

MAIN, SIDE = b'\x81\x49', b'\x81\x96'   # ！, ＊ (Shift-JIS 전각)
SKIP = re.compile(r'e501_\d{2}')        # 마을 사람 대사 갱신 등

def classify(s, e, ev):
    if not re.fullmatch(r'e\d{3}_\d{2}', ev) or SKIP.fullmatch(ev): return None
    if e == 0: return None               # 끝 조건이 없으면 끝난 뒤에도 계속 보이므로 제외
    if s == 0 or 0 < e - s <= 10: return MAIN   # 이 이벤트가 바로 다음 단계로 넘김
    return SIDE                          # 스토리 진행(장 단위 플래그 등)으로 닫힘 → 지금만 볼 수 있음

def main(src, out):
    d, T = read(src); stat = {MAIN: 0, SIDE: 0}
    for ti in range(1, len(T)):
        if T[ti][0] != 0xD0: continue
        rows = T[ti][1]
        for i, r in enumerate(rows):
            s, e = struct.unpack_from('<HH', r, 0x3C)
            ev = r[0x44:0x54].split(b'\0')[0].decode('latin1')
            mark = classify(s, e, ev)
            if not mark: continue
            name = r[:0x20].split(b'\0')[0]
            new = name + b' ' + mark
            if len(new) > 0x1F: continue
            rb = bytearray(r); rb[:0x20] = new.ljust(0x20, b'\0'); rows[i] = bytes(rb); stat[mark] += 1
    open(out, 'wb').write(build(d, T))
    print(f'！ {stat[MAIN]}곳, ＊ {stat[SIDE]}곳 -> {out}')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
