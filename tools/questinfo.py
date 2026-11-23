"""이벤트 스크립트(.bf)에서 메인 퀘스트 플래그 구간 뽑기
COMM 1 = 플래그 켜기, COMM 97 = 메인 퀘스트 수락, COMM 99 = 메인 퀘스트 완료 (번호 < 100)
퀘스트 구간 = 수락 스크립트가 켜는 가장 작은 플래그 ~ 수락 이후 첫 완료 스크립트가 켜는 가장 큰 플래그"""
import struct, glob, os

def procs(path):
    d = open(path, 'rb').read(); n = struct.unpack_from('<I', d, 0x10)[0]
    labels, ins = [], []
    for i in range(n):
        t, es, cnt, off = struct.unpack_from('<4I', d, 0x20 + i*16)
        if t == 0:
            labels = [(d[off+k*es:off+k*es+24].split(b'\0')[0].decode('latin1'), struct.unpack_from('<I', d, off+k*es+24)[0]) for k in range(cnt)]
        if t == 2:
            ins = [struct.unpack_from('<HH', d, off+4*k) for k in range(cnt)]
    labels.sort(key=lambda x: x[1])
    res = {}
    for j, (nm, st) in enumerate(labels):
        en = labels[j+1][1] if j+1 < len(labels) else len(ins)
        calls, stack, k = [], [], st
        while k < en:
            op, arg = ins[k]
            if op == 0 and k+1 < len(ins):
                stack.append(struct.unpack('<i', struct.pack('<HH', *ins[k+1]))[0]); k += 2; continue
            if op == 29: stack.append(arg)
            elif op == 8: calls.append((arg, tuple(stack))); stack = []
            elif op in (10, 13, 7, 9, 11, 12): stack = []
            k += 1
        res[nm] = calls
    return res

def load(events_dir):
    P = {}
    for f in glob.glob(os.path.join(events_dir, 'e*/e*.bf')):
        if os.path.basename(f) == 'e910.bf': continue
        try: P.update(procs(f))
        except Exception: pass
    return P

def windows(P):
    lo, hi, afam = {}, {}, {}
    for nm, cs in P.items():
        for c, a in cs:
            if c == 97 and a and 0 < a[-1] < 100: afam[a[-1]] = min(afam.get(a[-1], 999), int(nm[1:4]))
    for nm, cs in sorted(P.items()):
        q_acc = [a[-1] for c, a in cs if c == 97 and a and 0 < a[-1] < 100]
        q_clr = [a[-1] for c, a in cs if c == 99 and a and 0 < a[-1] < 100]
        fl = [a[-1] for c, a in cs if c == 1 and a and 0 < a[-1] < 1000]
        for q in q_acc:
            if fl: lo[q] = min(lo.get(q, 9999), min(fl))
        for q in q_clr:      # 수락 이후 가장 먼저 나오는 완료 스크립트만 (후반 정리용 완료 처리는 무시)
            if fl and q not in hi and int(nm[1:4]) >= afam.get(q, 0): hi[q] = max(fl)
    return {q: (lo[q], hi[q]) for q in lo if q in hi and lo[q] <= hi[q]}


def tightest(W, flag):
    """flag를 포함하는 가장 좁은 퀘스트 구간 (없으면 None)"""
    c = [(b - a, q, a, b) for q, (a, b) in W.items() if a <= flag <= b]
    return min(c)[1:] if c else None

def story_sets(P):
    """이벤트 묶음(eXXX) → 그 스크립트들이 켜는 이야기 플래그(<1000), 그리고 스크립트가 켜는 모든 이야기 플래그 목록"""
    fam, allf = {}, set()
    for nm, cs in P.items():
        for c, a in cs:
            if c == 1 and a and 0 < a[-1] < 1000:
                fam.setdefault(nm[:4], set()).add(a[-1]); allf.add(a[-1])
    return fam, sorted(allf)
