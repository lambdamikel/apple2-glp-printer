#!/usr/bin/env python3
"""Build GLPTEST.dsk / GLPTEST.po - a bootable ProDOS test disk for the
Apple II Super Serial Card <-> Centronics GLP 3101 project.

PRODOS and BASIC.SYSTEM are copied out of an existing bootable ProDOS .dsk,
since they are Apple system files and are not redistributed here.

  usage: python3 build.py [path/to/bootable-prodos.dsk]
"""
import sys, os, re, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prodos as P
import tok

PRJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRCDIR = os.path.join(PRJ, 'src')
OUTDIR = os.path.join(PRJ, 'disk')
DEFAULT_DONOR = os.path.expanduser('~/git/perfect-paul-ii/disk/perfect-paul.dsk')
VOL = 'GLP.TEST'

PROGS = [('STARTUP', 'startup.bas'), ('LOOPBACK', 'loopback.bas'),
         ('FRAMING', 'framing-sweep.bas'), ('BAUD', 'baud-sweep.bas'),
         ('SMOKETEST', 'glp-smoketest.bas'), ('RXWATCH', 'rxwatch.bas'),
         ('DIRECT', 'direct.bas'), ('STDTEST', 'stdtest.bas'),
         ('PRSETUP', 'prsetup.bas')]


def validate(fn, src):
    bad = tok.check_variables(src)
    if bad:
        raise SystemExit(f'{fn}: variables collide with Applesoft keywords: {bad}')
    nums = [int(re.match(r'(\d+)', l).group(1)) for l in src.splitlines() if l.strip()]
    if nums != sorted(nums) or len(nums) != len(set(nums)):
        raise SystemExit(f'{fn}: line numbers not ascending/unique')
    tgts = set(int(m) for m in re.findall(r'(?:GOSUB|GOTO|THEN)\s*(\d+)', src))
    if not tgts <= set(nums):
        raise SystemExit(f'{fn}: dangling jump targets {sorted(tgts - set(nums))}')


def main(donor=DEFAULT_DONOR):
    src = P.Img(open(donor, 'rb').read())
    sysfiles = {}
    for e in P.dir_entries(src):
        if e.name in ('PRODOS', 'BASIC.SYSTEM'):
            sysfiles[e.name] = (e.ftype, e.aux, P.read_file(src, e))
    for n in ('PRODOS', 'BASIC.SYSTEM'):
        if n not in sysfiles:
            raise SystemExit(f'{donor}: no {n} on that volume')

    img = P.Img()
    img.wb(0, src.rb(0))                       # ProDOS boot loader
    img.wb(1, src.rb(1))
    free = list(range(7, P.NBLOCKS))
    entries = []

    def alloc():
        if not free:
            raise SystemExit('disk full')
        return free.pop(0)

    def put(data):
        if len(data) <= 512:
            b = alloc(); img.wb(b, data.ljust(512, b'\0'))
            return 1, b, 1
        chunks = [data[i:i + 512] for i in range(0, len(data), 512)]
        if len(chunks) > 256:
            raise SystemExit('file needs tree storage')
        key = alloc(); idx = bytearray(512)
        for i, c in enumerate(chunks):
            b = alloc(); img.wb(b, c.ljust(512, b'\0'))
            idx[i], idx[256 + i] = b & 0xFF, b >> 8
        img.wb(key, bytes(idx))
        return 2, key, len(chunks) + 1

    def add(name, ftype, aux, data):
        st, key, used = put(data)
        e = bytearray(39)
        e[0] = (st << 4) | len(name)
        e[1:1 + len(name)] = name.encode('ascii')
        e[16] = ftype
        struct.pack_into('<H', e, 17, key)
        struct.pack_into('<H', e, 19, used)
        e[21], e[22], e[23] = len(data) & 0xFF, (len(data) >> 8) & 0xFF, (len(data) >> 16) & 0xFF
        e[24:28] = P.pdate(); e[30] = 0xC3
        struct.pack_into('<H', e, 31, aux)
        e[33:37] = P.pdate()
        entries.append(bytes(e))
        print(f'  {name:<14} ${ftype:02X} aux ${aux:04X} {len(data):>6}B  {used:>2} blk')

    for n in ('PRODOS', 'BASIC.SYSTEM'):
        ft, ax, d = sysfiles[n]
        add(n, ft, ax, d)
    for name, fn in PROGS:
        text = open(os.path.join(SRCDIR, fn)).read()
        validate(fn, text)
        add(name, 0xFC, 0x0801, tok.tokenize(text))

    hdr = bytearray(39)
    hdr[0] = 0xF0 | len(VOL)
    hdr[1:1 + len(VOL)] = VOL.encode('ascii')
    hdr[24:28] = P.pdate()
    hdr[28], hdr[30], hdr[31], hdr[32] = 0x00, 0xC3, 39, 13
    struct.pack_into('<H', hdr, 33, len(entries))
    struct.pack_into('<H', hdr, 35, 6)
    struct.pack_into('<H', hdr, 37, P.NBLOCKS)

    slots = [bytes(hdr)] + entries
    for bi, blk in enumerate((2, 3, 4, 5)):
        buf = bytearray(512)
        struct.pack_into('<H', buf, 0, 0 if blk == 2 else blk - 1)
        struct.pack_into('<H', buf, 2, 0 if blk == 5 else blk + 1)
        for i in range(13):
            k = bi * 13 + i
            if k < len(slots):
                off = 4 + i * 39
                buf[off:off + 39] = slots[k]
                if k:
                    struct.pack_into('<H', buf, off + 37, blk)
        img.wb(blk, bytes(buf))

    bm = bytearray(512)
    for b in range(7, P.NBLOCKS):
        if b in free:
            bm[b >> 3] |= 0x80 >> (b & 7)
    img.wb(6, bytes(bm))

    os.makedirs(OUTDIR, exist_ok=True)
    dsk = os.path.join(OUTDIR, 'GLPTEST.dsk')
    open(dsk, 'wb').write(bytes(img.d))
    po = bytearray()
    for b in range(P.NBLOCKS):
        po += img.rb(b)
    open(os.path.join(OUTDIR, 'GLPTEST.po'), 'wb').write(bytes(po))

    chk = P.Img(open(dsk, 'rb').read())
    ok = all(P.read_file(chk, e) == tok.tokenize(open(os.path.join(SRCDIR, dict(
        (n, f) for n, f in PROGS)[e.name])).read())
        for e in P.dir_entries(chk) if e.stype != 15 and e.name in dict(PROGS))
    print(f'\nwrote {OUTDIR}/GLPTEST.dsk and .po  '
          f'({P.NBLOCKS - 7 - len(free)} blocks used)   verified: {ok}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DONOR))
