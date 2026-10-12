import struct
def names_of(ua):
    p = 0
    def i32():
        nonlocal p; v = struct.unpack_from('<i', ua, p)[0]; p += 4; return v
    def fstr():
        nonlocal p
        l = i32()
        if l < 0:
            s = ua[p:p - 2 * l].decode('utf-16-le')[:-1]; p += -2 * l
        else:
            s = ua[p:p + l].decode('latin-1')[:-1]; p += l
        return s
    tag = i32(); leg = i32(); ue3 = i32(); fv = i32(); lic = i32()
    n = i32(); p += n * 20
    total = i32(); folder = fstr(); flags = i32()
    ncount = i32(); noff = i32()
    p = noff
    names = []
    for _ in range(ncount):
        names.append(fstr()); p += 4
    return names, total

class DTReader:
    """Tagged-property reader for .uexp using the uasset name table."""
    def __init__(self, data, names):
        self.d = data; self.p = 0; self.n = names
    def i32(self): v = struct.unpack_from('<i', self.d, self.p)[0]; self.p += 4; return v
    def f32(self): v = struct.unpack_from('<f', self.d, self.p)[0]; self.p += 4; return v
    def u8(self): v = self.d[self.p]; self.p += 1; return v
    def fname(self):
        i = self.i32(); num = self.i32()
        s = self.n[i]
        return s if num == 0 else f"{s}_{num-1}"
    def fstr(self):
        l = self.i32()
        if l < 0:
            s = self.d[self.p:self.p - 2 * l].decode('utf-16-le')[:-1]; self.p += -2 * l
        else:
            s = self.d[self.p:self.p + l].decode('latin-1')[:-1]; self.p += l
        return s
    def props(self):
        out = {}
        while True:
            name = self.fname()
            if name == 'None': return out
            typ = self.fname(); size = self.i32(); idx = self.i32()
            key = name if idx == 0 else f"{name}[{idx}]"
            out[key] = self.body(typ, size)
    def body(self, typ, size):
        if typ == 'StructProperty':
            sn = self.fname(); self.p += 16; self.u8()
            st = self.p
            if sn in ('Vector', 'Vector2D', 'Guid', 'Color', 'LinearColor', 'Rotator'):
                self.p += size; return self.d[st:st + size]
            try:
                v = self.props()
            except Exception:
                v = None
            self.p = st + size; return v
        if typ == 'BoolProperty':
            v = self.u8(); self.u8(); return v
        if typ in ('ByteProperty', 'EnumProperty'):
            en = self.fname(); self.u8()
            if size == 1: return self.u8()
            return self.fname()
        if typ == 'ArrayProperty':
            inner = self.fname(); self.u8(); st = self.p
            cnt = self.i32(); vals = []
            try:
                if inner == 'StructProperty':
                    self.fname(); self.fname(); self.p += 8; self.fname(); self.p += 17
                    for _ in range(cnt): vals.append(self.props())
                else:
                    for _ in range(cnt): vals.append(self.body_scalar(inner))
            except Exception:
                vals = 'ERR'
            self.p = st + size; return vals
        self.u8(); st = self.p
        v = self.body_scalar(typ, size)
        if not (typ == 'TextProperty' and v is not None):
            # a plain FText is self-delimiting; Side Stories Helper's table stores a tag size
            # 10 bytes short on its edited rows, so trust the content, as the game does
            self.p = st + size
        return v
    def body_scalar(self, typ, size=None):
        if typ == 'IntProperty': return self.i32()
        if typ == 'FloatProperty': return self.f32()
        if typ == 'NameProperty': return self.fname()
        if typ == 'StrProperty': return self.fstr()
        if typ == 'BoolProperty': return self.u8()
        if typ == 'ByteProperty': return self.u8()
        if typ == 'EnumProperty': return self.fname()
        if typ == 'TextProperty':
            st = self.p
            flags = self.i32(); ht = self.u8()
            if ht == 0:
                ns = self.fstr(); key = self.fstr(); src = self.fstr(); return src
            if size: self.p = st + size
            return None
        if size is not None:
            self.p += size; return None
        raise ValueError(typ)

def read_datatable(ua, ue):
    names, _ = names_of(ua)
    r = DTReader(ue, names)
    r.props()          # object props
    r.i32()            # zero
    cnt = r.i32()
    rows = {}
    for _ in range(cnt):
        rn = r.fname()
        rows[rn] = r.props()
    return rows
