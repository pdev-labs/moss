#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Replace exact MUTF-8 strings inside a dex by rewriting the string-data section.

WHY
---
Dex `string_data_item`s are addressed only by the absolute offsets in `string_ids`,
so a string can be rewriting in place as long as the whole string-data region does
not grow. Rebuilding the section densely from its start and repointing every
`string_ids[i]` keeps everything else (type/code/class offsets) valid -- nothing
outside the region moves.

The spec here is a plain old->new byte map. New values must be <= old values in
aggregate (the region size is fixed); we abort if the rebuilt section would grow.

Header checksum/signature are recomputed (signature first; the checksum covers it).

Usage:
  dex_strings_patch.py in.dex out.dex --map "old=new" [--map ...]
  dex_strings_patch.py in.dex --list "needle"
"""

import argparse
import hashlib
import struct
import sys
import zlib


def u32(d, o):
    return struct.unpack_from("<I", d, o)[0]


def read_uleb128(d, p):
    n = 0
    shift = 0
    plen = 0
    while True:
        b = d[p]
        p += 1
        plen += 1
        n |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return n, plen, p


def enc_uleb128(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def read_item(d, off):
    """Return (payload_bytes, total_len) for the string_data_item at `off`."""
    n, plen, p = read_uleb128(d, off)
    start = p
    units = 0
    while units < n:
        b = d[p]
        if b & 0x80 == 0:
            p += 1
            units += 1
        elif (b & 0xE0) == 0xC0:
            p += 2
            units += 1
        elif (b & 0xF0) == 0xE0:
            p += 3
            units += 1
        else:
            raise ValueError("bad MUTF-8 byte 0x%02x at 0x%x" % (b, p))
    payload = bytes(d[start:p])
    total = plen + len(payload) + 1          # + NUL terminator
    return payload, total


def fix_header(d):
    d[12:32] = hashlib.sha1(bytes(d[32:])).digest()
    struct.pack_into("<I", d, 8, zlib.adler32(bytes(d[12:])) & 0xFFFFFFFF)


def list_strings(d, needle):
    ssize = u32(d, 56)
    soff = u32(d, 60)
    hits = 0
    for i in range(ssize):
        off = u32(d, soff + 4 * i)
        payload, _ = read_item(d, off)
        try:
            s = payload.decode("ascii")
        except UnicodeDecodeError:
            continue
        if needle in s:
            hits += 1
            print("  [%d] 0x%08x %r" % (i, off, s))
    print("%d/%d strings contain %r" % (hits, ssize, needle))


def patch(d, mapping):
    ssize = u32(d, 56)
    soff = u32(d, 60)
    offs = [u32(d, soff + 4 * i) for i in range(ssize)]

    unique = sorted(set(offs))
    items = {o: read_item(d, o) for o in unique}
    region_start = unique[0]
    region_end = max(o + items[o][1] for o in unique)
    region_len = region_end - region_start

    mapping_b = {k.encode("utf-8"): v.encode("utf-8") for k, v in mapping.items()}

    new_blob = bytearray()
    new_off = {}
    replaced = 0
    for o in unique:
        payload, total = items[o]
        if payload in mapping_b:
            nb = mapping_b[payload]
            item = enc_uleb128(len(nb)) + nb + b"\x00"
            replaced += 1
        else:
            item = bytes(d[o:o + total])
        new_off[o] = region_start + len(new_blob)
        new_blob += item

    if len(new_blob) > region_len:
        raise SystemExit("string-data region would grow by %d bytes; refusing"
                         % (len(new_blob) - region_len))

    d[region_start:region_start + len(new_blob)] = new_blob
    # zero any leftover tail so stale bytes cannot be mistaken for live strings
    if len(new_blob) < region_len:
        d[region_start + len(new_blob):region_end] = b"\x00" * (region_len - len(new_blob))

    for i, o in enumerate(offs):
        struct.pack_into("<I", d, soff + 4 * i, new_off[o])

    fix_header(d)
    return replaced, region_len - len(new_blob)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("dex")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--map", action="append", default=[])
    ap.add_argument("--list")
    args = ap.parse_args(argv[1:])

    d = bytearray(open(args.dex, "rb").read())
    if d[:4] != b"dex\n":
        raise SystemExit("not a dex: %s" % args.dex)

    if args.list is not None:
        list_strings(d, args.list)
        return 0

    mapping = {}
    for m in args.map:
        if "=" not in m:
            raise SystemExit("--map needs old=new, got %r" % m)
        k, v = m.split("=", 1)
        mapping[k] = v
    if not mapping:
        raise SystemExit("no --map given")

    replaced, slack = patch(d, mapping)
    if not args.out:
        args.out = args.dex + ".patched"
    open(args.out, "wb").write(bytes(d))
    print("dex strings: replaced %d string(s); %d byte(s) slack left in the region"
          % (replaced, slack))
    print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
