#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Replace a literal brand token inside resources.arsc's global string pool.

WHY
---
`resources.arsc` holds every string resource (all locales) in one chunked pool.
Renaming the app means rewriting those values. A full apktool/aapt2 rebuild is
slow and fragile here; instead we re-encode just the global string pool and patch
the RES_TABLE size. Everything else in the file addresses strings by *index*, not
by absolute offset, so shifting the pool is safe as long as the pool chunk's own
size and the table header size stay consistent.

Case-sensitive by default so the Italian/Spanish/Portuguese word "respiro"
(breath) is not clobbered while the brand "Respiro" is.

Usage:
  rebrand_strings.py in.apk out.apk --old Respiro --new Moss
  rebrand_strings.py in.apk --dump Respiro
"""

import argparse
import struct
import sys
import zipfile

RES_TABLE_TYPE = 0x0002
CHUNK_STRING_POOL = 0x0001


def u16(d, o):
    return struct.unpack_from("<H", d, o)[0]


def u32(d, o):
    return struct.unpack_from("<I", d, o)[0]


def find_global_pool(data):
    ctype, hsize, _size = struct.unpack_from("<HHI", data, 0)
    if ctype != RES_TABLE_TYPE:
        raise SystemExit("not a resources.arsc (type=0x%04x)" % ctype)
    off = hsize
    ctype, _hsize, csize = struct.unpack_from("<HHI", data, off)
    if ctype != CHUNK_STRING_POOL:
        raise SystemExit("first chunk after header is not a string pool (0x%04x)" % ctype)
    return off, csize


def parse_pool(data, off):
    ctype, hsize, csize = struct.unpack_from("<HHI", data, off)
    sc, stc, flags, sstart, styles_start = struct.unpack_from("<IIIII", data, off + 8)
    utf8 = bool(flags & 0x100)
    sorted_flag = bool(flags & 0x1)
    offs = [u32(data, off + 28 + 4 * i) for i in range(sc)]
    base = off + sstart
    strings = []
    for o in offs:
        p = base + o
        if utf8:
            l0 = data[p]
            p += 2 if (l0 & 0x80) else 1
            l1 = data[p]
            if l1 & 0x80:
                blen = ((l1 & 0x7F) << 8) | data[p + 1]
                p += 2
            else:
                blen = l1
                p += 1
            strings.append(data[p:p + blen].decode("utf-8", "replace"))
        else:
            ln = u16(data, p)
            strings.append(data[p + 2:p + 2 + ln * 2].decode("utf-16-le", "replace"))
    return {"off": off, "size": csize, "flags": flags, "utf8": utf8,
            "sorted": sorted_flag, "styles": stc, "strings": strings}


def encode_len(n):
    return bytes([n]) if n < 0x80 else bytes([(n >> 8) | 0x80, n & 0xFF])


def build_pool(strings, flags):
    utf8 = bool(flags & 0x100)
    data = bytearray()
    offs = []
    for s in strings:
        offs.append(len(data))
        if utf8:
            b = s.encode("utf-8")
            data += encode_len(len(s.encode("utf-16-le")) // 2) + encode_len(len(b)) + b + b"\x00"
        else:
            data += struct.pack("<H", len(s)) + s.encode("utf-16-le") + b"\x00\x00"
    sc = len(strings)
    stc = 0
    strings_start = 28 + 4 * sc + 4 * stc
    size = strings_start + len(data)
    # A resource table must be 4-byte aligned: libandroidfw rejects an arsc whose
    # chunk/total size is not a multiple of 4 ("not on an integer boundary").
    # Pad the tail of the string data (no offset ever points into it).
    pad = (-size) % 4
    if pad:
        data += b"\x00" * pad
        size += pad
    out = bytearray()
    out += struct.pack("<HHI", CHUNK_STRING_POOL, 28, size)
    out += struct.pack("<IIIII", sc, stc, flags, strings_start, 0)
    out += b"".join(struct.pack("<I", o) for o in offs)
    out += data
    return bytes(out)


def dump(data, needle):
    off, _ = find_global_pool(data)
    pool = parse_pool(data, off)
    n = 0
    for i, s in enumerate(pool["strings"]):
        if needle in s:
            n += 1
            if n <= 20:
                print("  [%d] %r" % (i, s[:120]))
    print("pool: %d strings, %d contain %r" % (len(pool["strings"]), n, needle))


def rebrand(data, old, new):
    off, _csize = find_global_pool(data)
    pool = parse_pool(data, off)
    strings = [s.replace(old, new) if old in s else s for s in pool["strings"]]
    changed = sum(1 for a, b in zip(pool["strings"], strings) if a != b)

    new_pool = build_pool(strings, pool["flags"])
    prefix = bytearray(data[:off])          # RES_TABLE header (12 bytes)
    suffix = bytearray(data[off + pool["size"]:])
    new_size = len(prefix) + len(new_pool) + len(suffix)
    struct.pack_into("<I", prefix, 4, new_size)   # RES_TABLE.size
    out = bytes(prefix) + new_pool + bytes(suffix)
    return out, changed, pool["sorted"]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("apk")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--old", default="Respiro")
    ap.add_argument("--new", default="Moss")
    ap.add_argument("--dump")
    args = ap.parse_args(argv[1:])

    with zipfile.ZipFile(args.apk) as z:
        arsc = z.read("resources.arsc")
        infos = list(z.infolist())

    if args.dump is not None:
        dump(arsc, args.dump)   # explicit needle ("" prints none)
        return 0

    new_arsc, changed, is_sorted = rebrand(arsc, args.old, args.new)
    if is_sorted:
        raise SystemExit("pool is sorted-flagged; a content change would break binary search")
    print("arsc: replaced %r->%r in %d string(s); %d -> %d bytes"
          % (args.old, args.new, changed, len(arsc), len(new_arsc)))

    with zipfile.ZipFile(args.apk) as src, zipfile.ZipFile(args.out, "w") as zo:
        for info in infos:
            data = new_arsc if info.filename == "resources.arsc" else src.read(info.filename)
            zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            zo.writestr(zi, data)
    print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
