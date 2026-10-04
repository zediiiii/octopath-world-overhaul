"""Minimal UE4 GVAS save parser / writer (lossless round-trip) for Octopath Traveler."""
import struct
import uuid

NATIVE_STRUCTS = {
    "Vector": 12, "Vector2D": 8, "Rotator": 12, "Quat": 16, "Guid": 16,
    "DateTime": 8, "Timespan": 8, "LinearColor": 16, "Color": 4, "IntPoint": 8,
    "Vector4": 16, "Box": 25,
}


class Reader:
    def __init__(self, data, pos=0):
        self.d = data
        self.p = pos

    def read(self, n):
        b = self.d[self.p:self.p + n]
        if len(b) != n:
            raise EOFError
        self.p += n
        return b

    def i32(self): return struct.unpack("<i", self.read(4))[0]
    def u32(self): return struct.unpack("<I", self.read(4))[0]
    def i64(self): return struct.unpack("<q", self.read(8))[0]
    def u16(self): return struct.unpack("<H", self.read(2))[0]
    def u8(self): return self.read(1)[0]
    def f32(self): return struct.unpack("<f", self.read(4))[0]

    def fstr(self):
        n = self.i32()
        if n == 0:
            return None if False else ""
        if n > 0:
            if n > 100000:
                raise ValueError("bad string len")
            s = self.read(n)
            return s[:-1].decode("latin-1")
        n = -n
        if n > 100000:
            raise ValueError("bad string len")
        s = self.read(n * 2)
        return s[:-2].decode("utf-16-le") + "\x00UTF16"


class Writer:
    def __init__(self):
        self.parts = []

    def raw(self, b): self.parts.append(bytes(b))
    def i32(self, v): self.raw(struct.pack("<i", v))
    def u32(self, v): self.raw(struct.pack("<I", v))
    def i64(self, v): self.raw(struct.pack("<q", v))
    def u16(self, v): self.raw(struct.pack("<H", v))
    def u8(self, v): self.raw(bytes([v]))
    def f32(self, v): self.raw(struct.pack("<f", v))

    def fstr(self, s):
        if s == "":
            self.i32(0)
            return
        if s.endswith("\x00UTF16"):
            b = s[:-6].encode("utf-16-le") + b"\x00\x00"
            self.i32(-(len(b) // 2))
            self.raw(b)
        else:
            b = s.encode("latin-1") + b"\x00"
            self.i32(len(b))
            self.raw(b)

    def bytes(self): return b"".join(self.parts)


class Prop:
    """A property. `value` depends on type:
    Int/UInt32/Float/Bool/Str/Name/Int64: python scalar
    Struct: list[Prop] (or raw bytes for native structs)
    Array: list of elements (scalars / list[Prop] / raw)
    Byte/Enum: scalar or string
    Other: raw bytes
    """

    def __init__(self, name, type_, **kw):
        self.name = name
        self.type = type_
        self.__dict__.update(kw)

    def __repr__(self):
        return f"Prop({self.name!r},{self.type!r})"

    def get(self, name):
        for p in self.value:
            if p.name == name:
                return p
        return None


def read_props(r, end=None):
    props = []
    while True:
        name = r.fstr()
        if name == "None":
            return props
        typ = r.fstr()
        size = r.i32()
        index = r.i32()
        props.append(read_prop_body(r, name, typ, size, index))


def read_prop_body(r, name, typ, size, index):
    p = Prop(name, typ, index=index)
    if typ == "StructProperty":
        p.struct_name = r.fstr()
        p.guid = r.read(16)
        p.has_guid = r.u8()
        if p.has_guid:
            p.pguid = r.read(16)
        start = r.p
        p.value = read_struct_value(r, p.struct_name, size)
        assert r.p == start + size, (name, r.p, start + size)
    elif typ == "BoolProperty":
        p.value = r.u8()
        p.has_guid = r.u8()
        if p.has_guid:
            p.pguid = r.read(16)
    elif typ in ("ByteProperty", "EnumProperty"):
        p.enum_name = r.fstr()
        p.has_guid = r.u8()
        if p.has_guid:
            p.pguid = r.read(16)
        if typ == "ByteProperty" and p.enum_name == "None":
            p.value = r.u8()
        else:
            p.value = r.fstr()
    elif typ == "ArrayProperty":
        p.inner = r.fstr()
        p.has_guid = r.u8()
        if p.has_guid:
            p.pguid = r.read(16)
        start = r.p
        try:
            p.value = read_array(r, p, size)
            if r.p != start + size:
                raise ValueError
            p.raw = False
        except Exception:
            r.p = start
            p.value = r.read(size)
            p.raw = True
    elif typ == "MapProperty":
        p.key_type = r.fstr()
        p.val_type = r.fstr()
        p.has_guid = r.u8()
        if p.has_guid:
            p.pguid = r.read(16)
        p.value = r.read(size)
    else:
        p.has_guid = r.u8()
        if p.has_guid:
            p.pguid = r.read(16)
        start = r.p
        if typ == "IntProperty":
            p.value = r.i32()
        elif typ == "UInt32Property":
            p.value = r.u32()
        elif typ == "Int64Property":
            p.value = r.i64()
        elif typ == "FloatProperty":
            p.value = r.f32()
        elif typ in ("StrProperty", "NameProperty"):
            p.value = r.fstr()
        else:
            p.value = r.read(size)
        assert r.p == start + size, (name, typ, r.p, start + size)
    return p


def read_struct_value(r, struct_name, size):
    if struct_name in NATIVE_STRUCTS:
        return r.read(size)
    start = r.p
    try:
        v = read_props(r)
        if r.p != start + size:
            raise ValueError
        return v
    except Exception:
        r.p = start
        return r.read(size)


def read_array(r, p, size):
    count = r.i32()
    inner = p.inner
    if inner == "StructProperty":
        p.a_name = r.fstr()
        p.a_type = r.fstr()
        p.a_size = r.i64()
        p.a_struct = r.fstr()
        p.a_guid = r.read(16)
        p.a_hasguid = r.u8()
        if p.a_hasguid:
            p.a_pguid = r.read(16)
        elems = []
        per = p.a_size // count if count else 0
        for _ in range(count):
            if p.a_struct in NATIVE_STRUCTS:
                elems.append(r.read(NATIVE_STRUCTS[p.a_struct]))
            else:
                elems.append(read_props(r))
        return elems
    elems = []
    for _ in range(count):
        if inner == "IntProperty":
            elems.append(r.i32())
        elif inner == "UInt32Property":
            elems.append(r.u32())
        elif inner == "FloatProperty":
            elems.append(r.f32())
        elif inner == "BoolProperty":
            elems.append(r.u8())
        elif inner == "ByteProperty":
            elems.append(r.u8())
        elif inner in ("StrProperty", "NameProperty", "EnumProperty"):
            elems.append(r.fstr())
        else:
            raise ValueError("unknown array inner " + inner)
    return elems


# ---------------- writing ----------------

def write_props(w, props):
    for p in props:
        write_prop(w, p)
    w.fstr("None")


def _guid(w, p):
    w.u8(p.has_guid)
    if p.has_guid:
        w.raw(p.pguid)


def write_prop(w, p):
    w.fstr(p.name)
    w.fstr(p.type)
    body = Writer()
    t = p.type
    if t == "StructProperty":
        if isinstance(p.value, (bytes, bytearray)):
            body.raw(p.value)
        else:
            write_props(body, p.value)
        b = body.bytes()
        w.i32(len(b)); w.i32(p.index)
        w.fstr(p.struct_name); w.raw(p.guid); _guid(w, p)
        w.raw(b)
    elif t == "BoolProperty":
        w.i32(0); w.i32(p.index)
        w.u8(p.value); _guid(w, p)
    elif t in ("ByteProperty", "EnumProperty"):
        if t == "ByteProperty" and p.enum_name == "None":
            body.u8(p.value)
        else:
            body.fstr(p.value)
        b = body.bytes()
        w.i32(len(b)); w.i32(p.index)
        w.fstr(p.enum_name); _guid(w, p); w.raw(b)
    elif t == "ArrayProperty":
        if getattr(p, "raw", False):
            body.raw(p.value)
        else:
            write_array(body, p)
        b = body.bytes()
        w.i32(len(b)); w.i32(p.index)
        w.fstr(p.inner); _guid(w, p); w.raw(b)
    elif t == "MapProperty":
        b = p.value
        w.i32(len(b)); w.i32(p.index)
        w.fstr(p.key_type); w.fstr(p.val_type); _guid(w, p); w.raw(b)
    else:
        if t == "IntProperty":
            body.i32(p.value)
        elif t == "UInt32Property":
            body.u32(p.value)
        elif t == "Int64Property":
            body.i64(p.value)
        elif t == "FloatProperty":
            body.f32(p.value)
        elif t in ("StrProperty", "NameProperty"):
            body.fstr(p.value)
        else:
            body.raw(p.value)
        b = body.bytes()
        w.i32(len(b)); w.i32(p.index)
        _guid(w, p); w.raw(b)


def write_array(w, p):
    w.i32(len(p.value))
    inner = p.inner
    if inner == "StructProperty":
        eb = Writer()
        for e in p.value:
            if isinstance(e, (bytes, bytearray)):
                eb.raw(e)
            else:
                write_props(eb, e)
        b = eb.bytes()
        w.fstr(p.a_name); w.fstr(p.a_type); w.i64(len(b))
        w.fstr(p.a_struct); w.raw(p.a_guid); w.u8(p.a_hasguid)
        if p.a_hasguid:
            w.raw(p.a_pguid)
        w.raw(b)
        return
    for e in p.value:
        if inner == "IntProperty":
            w.i32(e)
        elif inner == "UInt32Property":
            w.u32(e)
        elif inner == "FloatProperty":
            w.f32(e)
        elif inner in ("BoolProperty", "ByteProperty"):
            w.u8(e)
        else:
            w.fstr(e)


class SaveFile:
    def __init__(self, data):
        r = Reader(data)
        assert r.read(4) == b"GVAS"
        self.save_ver = r.i32()
        self.pkg_ver = r.i32()
        self.eng = (r.u16(), r.u16(), r.u16(), r.u32())
        self.branch = r.fstr()
        self.cv_format = r.i32()
        n = r.i32()
        self.custom = [(r.read(16), r.i32()) for _ in range(n)]
        self.class_name = r.fstr()
        self.props = read_props(r)
        self.trailer = data[r.p:]

    @classmethod
    def load(cls, path):
        with open(path, "rb") as f:
            return cls(f.read())

    def to_bytes(self):
        w = Writer()
        w.raw(b"GVAS"); w.i32(self.save_ver); w.i32(self.pkg_ver)
        w.u16(self.eng[0]); w.u16(self.eng[1]); w.u16(self.eng[2]); w.u32(self.eng[3])
        w.fstr(self.branch); w.i32(self.cv_format); w.i32(len(self.custom))
        for g, v in self.custom:
            w.raw(g); w.i32(v)
        w.fstr(self.class_name)
        write_props(w, self.props)
        w.raw(self.trailer)
        return w.bytes()

    def get(self, name):
        for p in self.props:
            if p.name == name:
                return p
        return None


def dump(props, indent=0, maxarr=6, out=None):
    pad = "  " * indent
    for p in props:
        v = p.value
        if p.type == "StructProperty" and isinstance(v, list):
            out.append(f"{pad}{p.name} <{p.struct_name}>")
            dump(v, indent + 1, maxarr, out)
        elif p.type == "ArrayProperty" and getattr(p, "raw", False):
            out.append(f"{pad}{p.name} [{p.inner}] RAW {len(v)} bytes: {bytes(v[:64]).hex()}")
        elif p.type == "ArrayProperty":
            out.append(f"{pad}{p.name} [{p.inner}{'/' + p.a_struct if p.inner == 'StructProperty' else ''}] n={len(v)}")
            for i, e in enumerate(v[:maxarr]):
                if isinstance(e, list):
                    out.append(f"{pad}  [{i}]")
                    dump(e, indent + 2, maxarr, out)
                else:
                    out.append(f"{pad}  [{i}] {e!r}"[:200])
        else:
            s = repr(v)
            if len(s) > 120:
                s = s[:120] + "..."
            out.append(f"{pad}{p.name} ({p.type}) = {s}")
    return out
