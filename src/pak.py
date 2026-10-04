import struct, zlib
class Pak:
    def __init__(self, path):
        self.f = open(path, 'rb')
        f = self.f
        f.seek(0, 2); n = f.tell(); f.seek(n - 44)
        magic, ver, off, size = struct.unpack('<IiQQ', f.read(24))
        f.seek(off); idx = f.read(size)
        p = 0
        def fstr():
            nonlocal p
            l = struct.unpack_from('<i', idx, p)[0]; p += 4
            if l < 0:
                s = idx[p:p - l * 2].decode('utf-16-le')[:-1]; p += -l * 2
            else:
                s = idx[p:p + l].decode('latin-1')[:-1]; p += l
            return s
        self.mount = fstr()
        cnt = struct.unpack_from('<i', idx, p)[0]; p += 4
        self.entries = {}
        for _ in range(cnt):
            name = fstr()
            e = self._entry(idx, p); p = e.pop('_end')
            self.entries[name] = e

    def _entry(self, b, p):
        off, csize, usize, comp = struct.unpack_from('<qqqi', b, p); p += 28
        p += 20  # sha1
        blocks = []
        if comp:
            nb = struct.unpack_from('<i', b, p)[0]; p += 4
            for _ in range(nb):
                blocks.append(struct.unpack_from('<qq', b, p)); p += 16
        enc = b[p]; p += 1
        bsz = struct.unpack_from('<I', b, p)[0]; p += 4
        return dict(off=off, csize=csize, usize=usize, comp=comp, blocks=blocks, enc=enc, _end=p)

    def read(self, name):
        e = self.entries[name]
        f = self.f
        f.seek(e['off'])
        hdr = self._entry(f.read(65536), 0)
        hlen = hdr['_end']
        if not e['comp']:
            f.seek(e['off'] + hlen); return f.read(e['usize'])
        out = []
        for s, t in e['blocks']:
            f.seek(s); out.append(zlib.decompress(f.read(t - s)))
        return b''.join(out)
