"""Minimal ProDOS reader/writer for 140K .dsk images in DOS sector order."""
import struct, datetime

SECMAP = [(0, 14), (13, 12), (11, 10), (9, 8), (7, 6), (5, 4), (3, 2), (1, 15)]
NBLOCKS = 280


def offs(b):
    t, i = b // 8, b % 8
    s1, s2 = SECMAP[i]
    return t * 4096 + s1 * 256, t * 4096 + s2 * 256


class Img:
    def __init__(self, data=None):
        self.d = bytearray(data if data is not None else b'\0' * 143360)

    def rb(self, b):
        a, c = offs(b)
        return bytes(self.d[a:a + 256] + self.d[c:c + 256])

    def wb(self, b, data):
        assert len(data) == 512
        a, c = offs(b)
        self.d[a:a + 256] = data[:256]
        self.d[c:c + 256] = data[256:]


def pdate(dt=None):
    dt = dt or datetime.datetime.now()
    d = ((dt.year % 100) << 9) | (dt.month << 5) | dt.day
    t = (dt.hour << 8) | dt.minute
    return struct.pack('<HH', d, t)


class Entry:
    def __init__(self, raw, blk, idx):
        self.raw, self.blk, self.idx = raw, blk, idx
        self.stype = raw[0] >> 4
        self.nlen = raw[0] & 0xF
        self.name = raw[1:1 + self.nlen].decode('ascii', 'replace')
        self.ftype = raw[16]
        self.key = struct.unpack('<H', raw[17:19])[0]
        self.used = struct.unpack('<H', raw[19:21])[0]
        self.eof = raw[21] | (raw[22] << 8) | (raw[23] << 16)
        self.aux = struct.unpack('<H', raw[31:33])[0]


def dir_entries(img, start=2):
    out, b = [], start
    while b:
        blk = img.rb(b)
        nxt = struct.unpack('<H', blk[2:4])[0]
        for i in range(13):
            off = 4 + i * 39
            raw = blk[off:off + 39]
            if raw[0] >> 4:
                out.append(Entry(raw, b, i))
        b = nxt
    return out


def read_file(img, e):
    """Return file contents, honouring seedling/sapling/tree storage."""
    if e.stype == 1:
        return img.rb(e.key)[:e.eof]
    if e.stype == 2:
        idx = img.rb(e.key)
        out = bytearray()
        for i in range(256):
            bn = idx[i] | (idx[256 + i] << 8)
            out += img.rb(bn) if bn else b'\0' * 512
            if len(out) >= e.eof:
                break
        return bytes(out[:e.eof])
    if e.stype == 3:
        master = img.rb(e.key)
        out = bytearray()
        for i in range(128):
            mn = master[i] | (master[256 + i] << 8)
            if not mn:
                out += b'\0' * 512 * 256
            else:
                idx = img.rb(mn)
                for j in range(256):
                    bn = idx[j] | (idx[256 + j] << 8)
                    out += img.rb(bn) if bn else b'\0' * 512
            if len(out) >= e.eof:
                break
        return bytes(out[:e.eof])
    raise ValueError('storage type %d' % e.stype)
