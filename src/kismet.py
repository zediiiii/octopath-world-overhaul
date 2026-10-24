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


# ---- growing a function: code appended after END, reached by redirected statements -------
# Existing statements never move, so no jump target changes. A statement is redirected by
# overwriting it in place with JUMP <new code> plus unreachable padding of the same disk AND
# in-memory size (EX_Nothing is 1/1 byte, a local variable 5/9), so everything after it
# keeps its offset.

def spans(pkg, index):
    """-> [(in-memory offset, offset in the script, bytes, text)] of every statement,
    including any code after END."""
    off, size, _mem = pkg.script(index)
    code = pkg.ue[off:off + size]
    d = Disassembler(pkg, code)
    out = []
    while d.p < size:
        m, p0 = d.mem, d.p
        s = d.expr()
        out.append((m, p0, code[p0:d.p], s))
    return out


def mem_size(pkg, code):
    """In-memory size of a run of whole expressions."""
    d = Disassembler(pkg, code)
    while d.p < len(code):
        d.expr()
    return d.mem


def jump_padding(pkg, target, disk, mem, local):
    """JUMP target, padded to exactly disk / mem bytes with EX_Nothing and reads of local
    (an export index of a local variable of the function)."""
    locals_, extra = divmod(mem - disk, 4)
    nothing = disk - 5 - 5 * locals_
    if extra or nothing < 0:
        raise ValueError(f"cannot pad a jump to {disk} disk / {mem} memory bytes")
    code = b"\x06" + struct.pack("<I", target) + b"\x0b" * nothing \
        + (b"\x00" + struct.pack("<i", local)) * locals_
    assert len(code) == disk and mem_size(pkg, code) == mem
    return code


def replace_script(ua, ue, index, code):
    """-> (ua, ue) with the function's bytecode replaced by code (which may be longer):
    updates the script's two sizes, the export's SerialSize, later exports' SerialOffset
    and the summary's BulkDataStartOffset. Every other export stays byte-identical."""
    import datatable as dt
    pkg = Package(ua, ue)
    off, size, _mem = pkg.script(index)
    grow = len(code) - size
    out_ue = bytearray(ue[:off - 8]) + struct.pack("<ii", mem_size(pkg, code), len(code)) \
        + code + ue[off + size:]
    s = dt.package_summary(ua)
    out_ua = bytearray(ua)
    eo = s["ExportOffset"][1]
    e = pkg.exports[index - 1]
    for i, x in enumerate(pkg.exports):
        base = eo + i * 104
        if struct.unpack_from("<qq", out_ua, base + 28) != (x["size"], x["off"] + pkg.header):
            raise RuntimeError("export table layout not as expected")
        if i + 1 == index:
            struct.pack_into("<q", out_ua, base + 28, x["size"] + grow)
        elif x["off"] > e["off"]:
            struct.pack_into("<q", out_ua, base + 36, x["off"] + pkg.header + grow)
    bo, bv = s["BulkDataStartOffset"]
    struct.pack_into("<q", out_ua, bo, bv + grow)
    out_ua, out_ue = bytes(out_ua), bytes(out_ue)
    new = Package(out_ua, out_ue)
    for i, (a, b) in enumerate(zip(pkg.exports, new.exports)):
        if i + 1 != index and ue[a["off"]:a["off"] + a["size"]] != out_ue[b["off"]:b["off"] + b["size"]]:
            raise RuntimeError(f"replace_script: export {a['name']} changed")
    return out_ua, out_ue


def bad_jumps(pkg, index):
    """Statement-level JUMP / JUMPIFNOT / PUSHFLOW targets that don't land on a statement."""
    import re
    st = disassemble(pkg, index, past_end=True)
    starts = {m for m, _s in st}
    return [(m, s) for m, s in st
            for t in re.findall(r"^(?:JUMP|JUMPIFNOT|PUSHFLOW) (\d+)", s)
            if int(t) not in starts]


def assemble(pkg, start, parts):
    """Lay out new code that will sit at in-memory offset start. parts are bytes,
    ("label", name), ("jump", name or offset) or ("jumpifnot", name, condition bytes).
    -> (code, in-memory offset just past it)."""
    labels = {}
    for _ in range(2):                  # jump sizes are fixed, so the 2nd pass is final
        out, at = b"", start
        for x in parts:
            if isinstance(x, bytes):
                b = x
            elif x[0] == "label":
                labels[x[1]] = at
                continue
            elif x[0] == "jump":
                b = b"\x06" + struct.pack("<I", x[1] if isinstance(x[1], int) else labels.get(x[1], 0))
            else:
                b = b"\x07" + struct.pack("<I", labels.get(x[1], 0)) + x[2]
            out += b
            at += mem_size(pkg, b)
    return out, at
