#!/usr/bin/env python3
"""Add Centronics GLP printer setup to a bootable ProDOS disk image.

Inserts BASIC.SYSTEM and a STARTUP program that configures an Apple II Super
Serial Card for the GLP (7 data bits, odd parity), then chains to whatever
.SYSTEM file the disk booted before. Programs that print through PR# rather
than programming the card themselves will then work unmodified.

  usage: patch_disk.py IN.dsk OUT.dsk [--donor DISK] [--slot N] [--baud CODE]

--donor is any bootable ProDOS disk to copy BASIC.SYSTEM from; it is Apple
system software and is not shipped here.
"""
import sys, os, struct, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prodos as P, tok

SETUP = """10  REM  CONFIGURE THE SUPER SERIAL CARD FOR
20  REM  A CENTRONICS GLP, THEN CHAIN ON.
30  D$ =  CHR$ (4):C$ =  CHR$ (9)
40  PRINT D$;"PR#{slot}"
50  PRINT C$;"{baud}B": REM  BAUD RATE
60  PRINT C$;"1D": REM  7 DATA BITS, 1 STOP
70  PRINT C$;"1P": REM  ODD PARITY
80  PRINT C$;"LD": REM  PRINTER SW2-7 ADDS THE LF
90  PRINT C$;"2C": REM  250 MS PAUSE AFTER CR
100  PRINT C$;"80N": REM  80 COLUMNS
110  PRINT  CHR$ (27);"@";: REM  INITIALISE PRINTER
120  PRINT  CHR$ (27);"2": REM  1/6 IN - CR HERE IS DELIBERATE
130  PRINT D$;"PR#0"
140  HOME
150  PRINT "PRINTER: SLOT {slot}, 7 DATA, ODD PARITY"
160  FOR J = 1 TO 1200: NEXT J
170  PRINT D$;"-{target}"
"""


def boot_target(img):
    for e in P.dir_entries(img):
        if e.stype != 15 and e.ftype == 0xFF and e.name.endswith('.SYSTEM'):
            return e.name
    raise SystemExit('no bootable .SYSTEM file on that disk')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('dst')
    ap.add_argument('--donor', default=os.path.expanduser('~/prodos.dsk'))
    ap.add_argument('--slot', type=int, default=2)
    ap.add_argument('--baud', default='14', help='SSC code: 8=1200, 12=4800, 14=9600')
    a = ap.parse_args()

    img = P.Img(open(a.src, 'rb').read())
    target = boot_target(img)
    if target == 'BASIC.SYSTEM':
        raise SystemExit('disk already boots BASIC.SYSTEM - just replace its STARTUP')
    print(f'boot target is {target}')

    src = SETUP.format(slot=a.slot, baud=a.baud, target=target)
    bad = tok.check_variables(src)
    if bad:
        raise SystemExit(f'reserved-word variables: {bad}')
    data = tok.tokenize(src)

    bm = bytearray(img.rb(6))
    free = [b for b in range(P.NBLOCKS) if bm[b >> 3] & (0x80 >> (b & 7))]

    def alloc():
        if not free:
            raise SystemExit('disk full')
        b = free.pop(0); bm[b >> 3] &= ~(0x80 >> (b & 7)); return b

    def put(d):
        if len(d) <= 512:
            b = alloc(); img.wb(b, d.ljust(512, b'\0')); return 1, b, 1
        ch = [d[i:i+512] for i in range(0, len(d), 512)]
        key = alloc(); idx = bytearray(512)
        for i, c in enumerate(ch):
            b = alloc(); img.wb(b, c.ljust(512, b'\0'))
            idx[i], idx[256+i] = b & 0xFF, b >> 8
        img.wb(key, bytes(idx)); return 2, key, len(ch)+1

    def entry(name, ft, aux, d):
        st, key, used = put(d); e = bytearray(39)
        e[0] = (st << 4) | len(name); e[1:1+len(name)] = name.encode(); e[16] = ft
        struct.pack_into('<H', e, 17, key); struct.pack_into('<H', e, 19, used)
        e[21], e[22], e[23] = len(d) & 0xFF, (len(d) >> 8) & 0xFF, (len(d) >> 16) & 0xFF
        e[24:28] = P.pdate(); e[30] = 0xC3
        struct.pack_into('<H', e, 31, aux); e[33:37] = P.pdate()
        return bytes(e)

    donor = P.Img(open(a.donor, 'rb').read())
    bs = [e for e in P.dir_entries(donor) if e.name == 'BASIC.SYSTEM']
    if not bs:
        raise SystemExit(f'no BASIC.SYSTEM on {a.donor}')
    new = [entry('BASIC.SYSTEM', bs[0].ftype, bs[0].aux, P.read_file(donor, bs[0])),
           entry('STARTUP', 0xFC, 0x0801, data)]
    old = [e.raw for e in P.dir_entries(img) if e.stype != 15]
    h = bytearray(img.rb(2)[4:43]); struct.pack_into('<H', h, 33, len(new) + len(old))
    slots = [bytes(h)] + new + old
    if len(slots) > 4 * 13:
        raise SystemExit('volume directory full')
    for bi, blk in enumerate((2, 3, 4, 5)):
        buf = bytearray(512)
        struct.pack_into('<H', buf, 0, 0 if blk == 2 else blk - 1)
        struct.pack_into('<H', buf, 2, 0 if blk == 5 else blk + 1)
        for i in range(13):
            k = bi * 13 + i
            if k < len(slots):
                off = 4 + i * 39; buf[off:off+39] = slots[k]
                if k:
                    struct.pack_into('<H', buf, off + 37, blk)
        img.wb(blk, bytes(buf))
    img.wb(6, bytes(bm))

    open(a.dst, 'wb').write(bytes(img.d))
    po = bytearray()
    for b in range(P.NBLOCKS):
        po += img.rb(b)
    open(os.path.splitext(a.dst)[0] + '.po', 'wb').write(bytes(po))
    chk = P.Img(open(a.dst, 'rb').read())
    print('now boots:', boot_target(chk), '| free blocks:', len(free))
    print('wrote', a.dst, 'and .po')


if __name__ == '__main__':
    main()
