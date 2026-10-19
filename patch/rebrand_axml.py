#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rewrite an APK's binary AndroidManifest.xml: change the package id and the
visible app name (label), without a full apktool rebuild.

WHY
---
`apktool b` on a large R8/Compose app is slow and sometimes fails; all we need is
two edits inside one AXML file:
  1. the <manifest package="..."> string  -> install identity
  2. android:label on <application>/<activity> -> shown name

AXML is a small chunked format (string pool + resource map + XML nodes). We
re-encode only the string pool (indexes stay stable, so nothing else needs
rewriting) and flip the label attributes from a resource *reference* to a string
*literal*. The XML node chunks that follow the pool are copied verbatim; they
address strings by index and never by absolute offset, so moving them is safe.
The top-level file-size header is patched to match.

Usage:
  rebrand_axml.py in.apk out.apk --package org.moss.app --label Moss
  rebrand_axml.py in.apk --dump
"""

import argparse
import struct
import sys
import zipfile

CHUNK_STRING_POOL = 0x0001
CHUNK_XML_START_ELEMENT = 0x0102
TYPE_REFERENCE = 0x01
TYPE_STRING = 0x03
RES_VALUE_SIZE = 0x0008


def u16(d, o):
    return struct.unpack_from("<H", d, o)[0]


def u32(d, o):
    return struct.unpack_from("<I", d, o)[0]


def parse_pool(data, off):
    ctype, _hsize, csize = struct.unpack_from("<HHI", data, off)
    if ctype != CHUNK_STRING_POOL:
        raise ValueError("expected string pool at 0x%x, got 0x%04x" % (off, ctype))
    sc, stc, flags, sstart, _ststart = struct.unpack_from("<IIIII", data, off + 8)
    utf8 = bool(flags & 0x100)
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
    return {"off": off, "size": csize, "flags": flags,
            "strings": strings, "utf8": utf8}


def build_pool(strings, flags):
    utf8 = bool(flags & 0x100)
    data = bytearray()
    offs = []
    for s in strings:
        offs.append(len(data))
        if utf8:
            b = s.encode("utf-8")

            def el(n):
                return bytes([n]) if n < 0x80 else bytes([(n >> 8) | 0x80, n & 0xFF])
            data += el(len(s)) + el(len(b)) + b + b"\x00"
        else:
            data += struct.pack("<H", len(s)) + s.encode("utf-16-le") + b"\x00\x00"
    sc = len(strings)
    stc = 0
    strings_start = 28 + 4 * sc + 4 * stc
    size = strings_start + len(data)
    out = bytearray()
    out += struct.pack("<HHI", CHUNK_STRING_POOL, 28, size)
    out += struct.pack("<IIIII", sc, stc, flags, strings_start, 0)
    out += b"".join(struct.pack("<I", o) for o in offs)
    out += data
    return bytes(out)


def iter_chunks(data, start, end):
    off = start
    while off < end:
        _ctype, _hsize, csize = struct.unpack_from("<HHI", data, off)
        if csize == 0:
            break
        yield off, _ctype, csize
        off += csize


def scan_elements(data, start, end):
    for off, ctype, _csize in iter_chunks(data, start, end):
        if ctype != CHUNK_XML_START_ELEMENT:
            continue
        name_idx = u32(data, off + 20)
        attr_start = u16(data, off + 24)
        attr_size = u16(data, off + 26)
        attr_count = u16(data, off + 28)
        attrs = []
        for i in range(attr_count):
            # attributeStart is relative to the start of the attrExt, which
            # begins right after the 16-byte node header.
            a = off + 16 + attr_start + i * attr_size
            ns, nm, raw = struct.unpack_from("<III", data, a)
            _tsize, _res0, dtype = struct.unpack_from("<HBB", data, a + 12)
            ddata = u32(data, a + 16)
            attrs.append((a, nm, raw, dtype, ddata))
        yield off, name_idx, attrs


def first_index(strings, value):
    hits = [i for i, s in enumerate(strings) if s == value]
    return hits


def describe(strings, dtype, ddata):
    if dtype == TYPE_STRING and ddata < len(strings):
        return repr(strings[ddata])
    if dtype == TYPE_REFERENCE:
        return "ref@0x%08x" % ddata
    return "type=0x%02x data=0x%x" % (dtype, ddata)


def dump(data):
    pool = parse_pool(data, 8)
    strings = pool["strings"]
    fsize = u32(data, 4)
    print("file size %d, strings %d (utf8=%s)" % (fsize, len(strings), pool["utf8"]))
    for _off, name_idx, attrs in scan_elements(data, pool["off"] + pool["size"], fsize):
        el = strings[name_idx] if name_idx < len(strings) else "?%d" % name_idx
        for _a, nm, _raw, dtype, ddata in attrs:
            aname = strings[nm] if nm < len(strings) else "?%d" % nm
            if aname in ("package", "label"):
                print("  <%s %s=%s>" % (el, aname, describe(strings, dtype, ddata)))


def rebrand(data, new_package, new_label):
    if u16(data, 0) != 0x0003:
        raise SystemExit("not an AXML file (bad magic)")
    fsize = u32(data, 4)
    pool = parse_pool(data, 8)
    strings = list(pool["strings"])
    content_start = pool["off"] + pool["size"]

    pkg_hits = first_index(strings, "com.sgnoogle.respiro")
    if len(pkg_hits) != 1:
        raise SystemExit("package string not found or ambiguous: %r" % pkg_hits)
    pkg_idx = pkg_hits[0]

    label_name = first_index(strings, "label")
    if not label_name:
        raise SystemExit("no 'label' attribute name in pool")
    label_name_idx = label_name[0]

    app_name = first_index(strings, "application")
    if not app_name:
        raise SystemExit("no 'application' element name in pool")
    app_name_idx = app_name[0]

    app_label_ref = None
    label_sites = []
    for _off, name_idx, attrs in scan_elements(data, content_start, fsize):
        for a, nm, _raw, dtype, ddata in attrs:
            if nm == label_name_idx:
                label_sites.append((a, dtype, ddata))
                if name_idx == app_name_idx and dtype == TYPE_REFERENCE:
                    app_label_ref = ddata
    if app_label_ref is None:
        raise SystemExit("could not locate application android:label reference")

    label_idx = len(strings)
    strings.append(new_label)
    strings[pkg_idx] = new_package

    new_pool = build_pool(strings, pool["flags"])
    shift = len(new_pool) - pool["size"]
    rest = bytearray(data[content_start:])

    changed = 0
    for a, dtype, ddata in label_sites:
        if dtype == TYPE_REFERENCE and ddata == app_label_ref:
            rel = a + shift - content_start
            struct.pack_into("<I", rest, rel, label_idx)
            struct.pack_into("<H", rest, rel + 12, RES_VALUE_SIZE)
            rest[rel + 14] = 0
            rest[rel + 15] = TYPE_STRING
            struct.pack_into("<I", rest, rel + 16, label_idx)
            changed += 1
    if changed == 0:
        raise SystemExit("no label attribute referenced the application label")

    new_size = 8 + len(new_pool) + len(rest)
    out = bytearray()
    out += struct.pack("<HHI", 0x0003, 0x0008, new_size)
    out += new_pool
    out += rest
    return bytes(out), changed


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("apk")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--package")
    ap.add_argument("--label")
    ap.add_argument("--dump", action="store_true")
    args = ap.parse_args(argv[1:])

    with zipfile.ZipFile(args.apk) as z:
        ax = z.read("AndroidManifest.xml")
        infos = list(z.infolist())

    if args.dump:
        dump(ax)
        return 0

    if not (args.package and args.label and args.out):
        print("error: need --package, --label and an output apk (or --dump)")
        return 2

    newax, changed = rebrand(ax, args.package, args.label)
    print("rebrand: package -> %s, label -> %s (%d label site(s)); manifest %d -> %d bytes"
          % (args.package, args.label, changed, len(ax), len(newax)))

    with zipfile.ZipFile(args.apk) as src, zipfile.ZipFile(args.out, "w") as zo:
        for info in infos:
            data = newax if info.filename == "AndroidManifest.xml" else src.read(info.filename)
            zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            zo.writestr(zi, data)
    print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
