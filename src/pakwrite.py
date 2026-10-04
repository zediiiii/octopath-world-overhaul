"""Minimal UE4 pak (version 4) writer - uncompressed, unencrypted. Enough for data mods."""
import hashlib
import struct

MAGIC = 0x5A6F12E1
VERSION = 4


def _fstring(s):
    b = s.encode("latin-1") + b"\x00"
    return struct.pack("<i", len(b)) + b


def _entry(offset, size, sha):
    # Offset, Size, UncompressedSize, CompressionMethod, SHA1, Encrypted, CompressionBlockSize
    return (struct.pack("<qqqi", offset, size, size, 0) + sha +
            struct.pack("<BI", 0, 0))


def write_pak(path, files, mount="../../../"):
    """files: {path_inside_pak: bytes}"""
    records = []
    blob = []
    offset = 0
    for name, data in files.items():
        sha = hashlib.sha1(data).digest()
        header = _entry(0, len(data), sha)   # header stored before the data has Offset=0
        blob.append(header)
        blob.append(data)
        records.append((name, _entry(offset, len(data), sha)))
        offset += len(header) + len(data)
    body = b"".join(blob)

    index = _fstring(mount) + struct.pack("<i", len(records))
    for name, rec in records:
        index += _fstring(name) + rec
    index_sha = hashlib.sha1(index).digest()

    footer = (struct.pack("<B", 0) + struct.pack("<Ii", MAGIC, VERSION) +
              struct.pack("<qq", len(body), len(index)) + index_sha)

    with open(path, "wb") as f:
        f.write(body)
        f.write(index)
        f.write(footer)
    return len(body) + len(index) + len(footer)
