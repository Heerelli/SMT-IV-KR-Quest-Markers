"""진여신4(한국판) code.ips: 지도 아이콘 '발견' 검사(0x24D360)에서 방 번호가 63보다 크면 무조건 발견된 것으로 처리.
→ 방 번호 255로 넣은 목적지 마커는 미탐색 구역에서도 보임."""
import struct, sys
BASE = 0x100000
FUNC = 0x24D360
ORIG = [0xE92D4070,0xE1A05000,0xE1A04001,None,0xE0800185,0xE2800ECF,0xE7D011A4,
        0xE2043007,0xE3A02001,0xE1A00312,0xE20000FF,0xE0100001,0x13A00001,0xE8BD8070]
NEW_FROM_4 = [
    0xE354003F,  # cmp   r4, #63
    0x83A00001,  # movhi r0, #1
    0x88BD8070,  # pophi {r4-r6, pc}
    0xE0800185,  # add   r0, r0, r5, lsl #3
    0xE2800ECF,  # add   r0, r0, #0xCF0
    0xE7D011A4,  # ldrb  r1, [r0, r4, lsr #3]
    0xE2043007,  # and   r3, r4, #7
    0xE1A00331,  # mov   r0, r1, lsr r3
    0xE2000001,  # and   r0, r0, #1
    0xE8BD8070,  # pop   {r4-r6, pc}
]
def check(code):
    for i, w in enumerate(ORIG):
        if w is not None and struct.unpack_from('<I', code, FUNC - BASE + 4*i)[0] != w:
            raise SystemExit(f'원본과 다름 @ {hex(FUNC+4*i)} — 다른 버전의 code.bin')
# 2) 도쿄 필드(맵 101~103) 아이콘 로더(0x232174)는 행의 그림 번호를 무시하고 종류별로
#    7107(종류 5)/7108(종류 6)/7109(그 외, 노란 네모)를 강제로 씀 → 깃발이 노란 네모로 보였음.
#    행에 그림 번호가 있으면 그것을, 없으면(원래 필드 아이콘) 7102 + 종류(=7107/7108/7109)를 쓰게 바꿈.
FIELD = 0x23227C
FIELD_ORIG = [0xE3500005, 0x059F8194, 0x0A000002, 0xE3500006, 0x159F818C, 0x059F818C]
FIELD_NEW = [
    0xE1D480BA,  # ldrh  r8, [r4, #0xa]     행의 그림 번호
    0xE3580000,  # cmp   r8, #0
    0x02808C1B,  # addeq r8, r0, #0x1b00    없으면 종류 + 0x1BBE(7102)
    0x028880BE,  # addeq r8, r8, #0xbe
    0xE1A00000,  # nop
    0xE1A00000,  # nop
]
def check_field(code):
    for i, w in enumerate(FIELD_ORIG):
        if struct.unpack_from('<I', code, FIELD - BASE + 4*i)[0] != w:
            raise SystemExit(f'원본과 다름 @ {hex(FIELD+4*i)} — 다른 버전의 code.bin')
def rec(off, words):
    data = b''.join(struct.pack('<I', w) for w in words)
    return off.to_bytes(3, 'big') + len(data).to_bytes(2, 'big') + data
def ips():
    return b'PATCH' + rec(FUNC - BASE + 16, NEW_FROM_4) + rec(FIELD - BASE, FIELD_NEW) + b'EOF'
if __name__ == '__main__':
    code = open(sys.argv[1], 'rb').read(); check(code); check_field(code)
    open(sys.argv[2], 'wb').write(ips()); print('ok', sys.argv[2])
