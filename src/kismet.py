"""Read cooked UE 4.18 blueprints: the export table and Kismet bytecode.

Enough to find a function's script and disassemble it into readable statements, so a patch
can be checked against the exact code it expects before any byte is touched. In memory an
object reference is 8 bytes and a name 12; on disk they are 4 and 8, so the disassembler
tracks both offsets (jump targets are in-memory offsets).
"""
import struct

import datatable as dt
import uasset


class Package:
    def __init__(self, ua, ue):
        self.ua, self.ue = ua, ue
        self.names, _ = uasset.names_of(ua)
        s = dt.package_summary(ua)
        self.header = s["TotalHeaderSize"][1]
        self.imports = []
        o = s["ImportOffset"][1]
        for _ in range(s["ImportCount"][1]):
            _cp, _cpn, _cls, _cln, outer, nm, _nmn = struct.unpack_from("<7i", ua, o)
            o += 28
            self.imports.append(dict(outer=outer, name=self.names[nm]))
        self.exports = []
        o = s["ExportOffset"][1]
        for _ in range(s["ExportCount"][1]):
            cls, sup, _tpl, outer, nm, nmn, _flags = struct.unpack_from("<6iI", ua, o)
            size, off = struct.unpack_from("<qq", ua, o + 28)
            o += 28 + 16 + 12 + 16 + 4 + 4 + 4 + 20
            self.exports.append(dict(cls=cls, outer=outer, size=size, off=off - self.header,
                                     name=self.names[nm] + (f"_{nmn - 1}" if nmn else "")))

    def ref(self, i):
        if i < 0:
            return "imp:" + self.imports[-i - 1]["name"]
        if i > 0:
            return "exp:" + self.exports[i - 1]["name"]
        return "null"

    def export_index(self, name, cls=None, outer=None):
        """1-based index of the single export matching name (and class / outer names)."""
        hits = [i + 1 for i, e in enumerate(self.exports) if e["name"] == name
                and (cls is None or self.ref(e["cls"]).split(":")[-1] == cls)
                and (outer is None or self.ref(e["outer"]).split(":")[-1] == outer)]
        if len(hits) != 1:
            raise RuntimeError(f"export {name} ({cls}, {outer}): {len(hits)} matches")
        return hits[0]

    def script(self, index):
        """-> (offset of the bytecode in .uexp, disk size, in-memory size) of a function."""
        e = self.exports[index - 1]
        d = self.ue[e["off"]:e["off"] + e["size"]]
        # a UFunction ends with its bytecode then FunctionFlags + two ints; the bytecode is
        # preceded by its in-memory and on-disk sizes
        for x in range(8, len(d), 4):
            if struct.unpack_from("<i", d, x - 4)[0] == len(d) - 12 - x:
                return e["off"] + x, len(d) - 12 - x, struct.unpack_from("<i", d, x - 8)[0]
        raise RuntimeError(f"{e['name']}: no bytecode found")


class Disassembler:
    def __init__(self, pkg, code):
        self.k, self.c, self.p, self.mem = pkg, code, 0, 0

    def _u8(self):
        v = self.c[self.p]
        self.p += 1
        self.mem += 1
        return v

    def _num(self, fmt, size):
        v = struct.unpack_from(fmt, self.c, self.p)[0]
        self.p += size
        self.mem += size
        return v

    def _i32(self):
        return self._num("<i", 4)

    def _obj(self):
        v = struct.unpack_from("<i", self.c, self.p)[0]
        self.p += 4
        self.mem += 8
        return self.k.ref(v)

    def _name(self):
        i, n = struct.unpack_from("<ii", self.c, self.p)
        self.p += 8
        self.mem += 12
        return self.k.names[i] + (f"_{n - 1}" if n else "")

    def _until(self, end):
        out = []
        while self.c[self.p] != end:
            out.append(self.expr())
        self._u8()
        return out

    def expr(self):
        t = self._u8()
        E = self.expr
        if t in (0x00, 0x01, 0x02, 0x48):
            return {0x00: "local:", 0x01: "inst:", 0x02: "default:", 0x48: "out:"}[t] + self._obj()
        if t == 0x04:
            return f"RETURN {E()}"
        if t == 0x06:
            return f"JUMP {self._i32()}"
        if t == 0x07:
            j = self._i32()
            return f"JUMPIFNOT {j} ({E()})"
        if t == 0x09:
            self._num("<H", 2)
            self._u8()
            return f"ASSERT {E()}"
        if t == 0x0B:
            return "nothing"
        if t == 0x0F:
            self._obj()
            a = E()
            return f"LET {a} = {E()}"
        if t in (0x14, 0x5F, 0x60, 0x43, 0x44):
            a = E()
            return f"LET {a} = {E()}"
        if t in (0x12, 0x19, 0x1A):
            o = E()
            self._i32()
            self._obj()
            return f"{o}.{E()}"
        if t in (0x13, 0x2E, 0x52, 0x54, 0x55):
            c = self._obj()
            return f"cast<{c}>({E()})"
        if t == 0x15:
            return "endparm"
        if t == 0x17:
            return "self"
        if t == 0x18:
            self._i32()
            return f"skip({E()})"
        if t in (0x1B, 0x45):
            n = self._name()
            return f"{n}({', '.join(self._until(0x16))})"
        if t in (0x1C, 0x46, 0x68, 0x63):
            f = self._obj().split(":")[-1]
            return f"{f}({', '.join(self._until(0x16))})"
        if t == 0x1D:
            return str(self._i32())
        if t == 0x1E:
            return repr(self._num("<f", 4))
        if t == 0x1F:
            e = self.c.index(b"\0", self.p)
            s = self.c[self.p:e].decode("latin-1")
            n = e + 1 - self.p
            self.p += n
            self.mem += n
            return repr(s)
        if t == 0x34:
            e = self.p
            while self.c[e:e + 2] != b"\0\0":
                e += 2
            s = self.c[self.p:e].decode("utf-16-le")
            n = e + 2 - self.p
            self.p += n
            self.mem += n
            return repr(s)
        if t == 0x20:
            return f"obj:{self._obj()}"
        if t == 0x21:
            return f"name:{self._name()}"
        if t in (0x22, 0x23):
            return "vec(" + ",".join(str(self._num("<f", 4)) for _ in range(3)) + ")"
        if t in (0x24, 0x2C):
            return f"byte:{self._u8()}"
        if t in (0x25, 0x26, 0x27, 0x28, 0x2A, 0x2D):
            return {0x25: "0", 0x26: "1", 0x27: "true", 0x28: "false"}.get(t, "None")
        if t == 0x2F:
            s = self._obj()
            self._i32()
            return f"struct<{s}>({', '.join(self._until(0x30))})"
        if t == 0x31:
            v = E()
            return f"SETARRAY {v} = [{', '.join(self._until(0x32))}]"
        if t == 0x38:
            ty = self._u8()
            return f"pcast{ty}({E()})"
        if t == 0x42:
            pr = self._obj().split(":")[-1]
            return f"{E()}.{pr}"
        if t == 0x4C:
            return f"PUSHFLOW {self._i32()}"
        if t == 0x4D:
            return "POPFLOW"
        if t == 0x4E:
            return f"COMPUTEDJUMP {E()}"
        if t == 0x4F:
            return f"POPFLOWIFNOT {E()}"
        if t == 0x51:
            return f"iface({E()})"
        if t == 0x53:
            return "END"
        if t in (0x50, 0x5A, 0x5E):
            return "trace"
        if t == 0x5B:
            return f"skipoff {self._i32()}"
        if t == 0x64:
            pr = self._obj()
            return f"PERSIST {pr} = {E()}"
        if t == 0x65:
            self._obj()
            self._i32()
            return f"[{', '.join(self._until(0x66))}]"
        if t == 0x69:
            n = self._num("<H", 2)
            self._i32()
            idx = E()
            cases = []
            for _ in range(n):
                cv = E()
                self._i32()
                cases.append(f"{cv}:{E()}")
            return f"switch({idx}){{{'; '.join(cases)}; default:{E()}}}"
        if t == 0x6A:
            self._u8()
            return "instr"
        if t == 0x6B:
            a = E()
            return f"{a}[{E()}]"
        raise ValueError(f"unknown Kismet token {t:#x} at byte {self.p - 1}")

    def statements(self, past_end=False):
        """-> [(in-memory offset, text)] up to and including END (or the whole script:
        code can be appended after END and reached by a jump)."""
        out = []
        while self.p < len(self.c):
            m = self.mem
            s = self.expr()
            out.append((m, s))
            if s == "END" and not past_end:
                break
        return out


def disassemble(pkg, index, past_end=False):
    off, size, mem = pkg.script(index)
    d = Disassembler(pkg, pkg.ue[off:off + size])
    st = d.statements(past_end)
    if d.mem != mem or d.p != size:
        raise RuntimeError(f"disassembly out of step: {d.p}/{size} bytes, {d.mem}/{mem} memory")
    return st
