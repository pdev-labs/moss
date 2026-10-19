#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Replace exact strings in a dex while keeping the file valid for ART.

TWO constraints drive this design
---------------------------------
1. Android's verifier requires `string_ids` to be sorted by string content
   (UTF-16 code-unit order).  Changing a string can push it out of order and
   dexopt then fails with "Out-of-order string_ids: 'A' then 'B'".
2. A `string_data_item` addressed by `string_ids` may not simply be overwritten
   when the replacement is longer.

So we rebuild the *string_data region only* (which is a fixed, self-contained
byte range addressed exclusively by absolute offsets in `string_ids`), then
re-sort the smallest string_ids window that restores order, then remap every
reference to the indices that moved.

Because the region is addressed only via `string_ids`, nothing outside it has to
move, as long as the rebuilt region does not grow.  A single replacement may be
longer than the original provided the *net* growth across the whole region is
<= 0 (the region is padded if it shrinks).  `string_ids` entries are permuted in
place, so the file size never changes.  Header checksum + SHA-1 are recomputed.

Usage:
  dex_strings_sorted_patch.py in.dex out.dex --map "old=new" [--map ...]
"""

import argparse
import hashlib
import struct
import sys
import zlib


# ---------------------------------------------------------------- primitives

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


def mutf8_units(b):
    """Decode MUTF-8 payload bytes to their UTF-16 code-unit sequence."""
    out = []
    i = 0
    n = len(b)
    while i < n:
        c = b[i]
        if c & 0x80 == 0:
            out.append(c)
            i += 1
        elif c & 0xE0 == 0xC0:
            out.append(((c & 0x1F) << 6) | (b[i + 1] & 0x3F))
            i += 2
        elif c & 0xF0 == 0xE0:
            out.append(((c & 0x0F) << 12) |
                       ((b[i + 1] & 0x3F) << 6) | (b[i + 2] & 0x3F))
            i += 3
        else:
            raise ValueError("bad MUTF-8 byte 0x%02x" % c)
    return out


def sort_key(payload):
    """dex string ordering: UTF-16 code units, compared lexicographically."""
    return mutf8_units(payload)


def read_string_data(d, off):
    """Return (payload_bytes, total_item_len) for the string_data_item at off."""
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
    return bytes(d[start:p]), plen + (p - start) + 1


def fix_header(d):
    d[12:32] = hashlib.sha1(bytes(d[32:])).digest()
    struct.pack_into("<I", d, 8, zlib.adler32(bytes(d[12:])) & 0xFFFFFFFF)


# ------------------------------------------------- dalvik instruction widths

def build_widths():
    w = [1] * 256
    two = [0x02, 0x05, 0x08, 0x13, 0x15, 0x16, 0x19, 0x1A, 0x1C, 0x1F, 0x20,
           0x22, 0x23, 0x29, 0x2D, 0x2E, 0x2F, 0x30, 0x31, 0x32, 0x33, 0x34,
           0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0xFE, 0xFF]
    three = [0x03, 0x06, 0x09, 0x14, 0x17, 0x1B, 0x24, 0x25, 0x26, 0x2A, 0x2B,
             0x2C, 0x6E, 0x6F, 0x70, 0x71, 0x72, 0x74, 0x75, 0x76, 0x77, 0x78,
             0xFC, 0xFD]
    for o in two:
        w[o] = 2
    for o in three:
        w[o] = 3
    for o in range(0x44, 0x52):     # aget/aput family    23x
        w[o] = 2
    for o in range(0x52, 0x60):     # iget/iput family    22c
        w[o] = 2
    for o in range(0x60, 0x6E):     # sget/sput family    21c
        w[o] = 2
    for o in range(0x90, 0xB0):     # binop               23x
        w[o] = 2
    for o in range(0xD0, 0xD8):     # binop/lit16         22s
        w[o] = 2
    for o in range(0xD8, 0xE3):     # binop/lit8          22b
        w[o] = 2
    w[0x18] = 5                     # const-wide          51l
    w[0xFA] = 4                     # invoke-polymorphic  45cc
    w[0xFB] = 4                     # invoke-polymorphic/range 4rcc
    return w


WIDTHS = build_widths()


def iter_code_items(d):
    """Yield (insns_off, insns_size) for every code_item in the dex."""
    cd_size = u32(d, 0x60)
    cd_off = u32(d, 0x64)
    seen = set()
    for i in range(cd_size):
        base = cd_off + 32 * i
        class_data_off = u32(d, base + 24)
        if class_data_off == 0 or class_data_off in seen:
            continue
        seen.add(class_data_off)
        p = class_data_off
        sf, _, p = read_uleb128(d, p)
        inf, _, p = read_uleb128(d, p)
        dm, _, p = read_uleb128(d, p)
        vm, _, p = read_uleb128(d, p)
        for _ in range(sf + inf):
            _, _, p = read_uleb128(d, p)
            _, _, p = read_uleb128(d, p)
        for count in (dm, vm):
            for _ in range(count):
                _, _, p = read_uleb128(d, p)     # method_idx_diff
                _, _, p = read_uleb128(d, p)     # access_flags
                code_off, _, p = read_uleb128(d, p)
                if code_off:
                    yield code_off + 16, u32(d, code_off + 12)


def remap_const_strings(d, perm):
    """Rewrite `const-string`/`const-string/jumbo` operands using perm[]."""
    touched = 0
    for insns_off, insns_size in iter_code_items(d):
        i = 0
        while i < insns_size:
            unit = struct.unpack_from("<H", d, insns_off + 2 * i)[0]
            op = unit & 0xFF
            if unit == 0x0100:                       # packed-switch payload
                size = struct.unpack_from("<H", d, insns_off + 2 * (i + 1))[0]
                i += 4 + size * 2
                continue
            if unit == 0x0200:                       # sparse-switch payload
                size = struct.unpack_from("<H", d, insns_off + 2 * (i + 1))[0]
                i += 2 + size * 4
                continue
            if unit == 0x0300:                       # fill-array-data payload
                ew = struct.unpack_from("<H", d, insns_off + 2 * (i + 1))[0]
                sz = u32(d, insns_off + 2 * (i + 2))
                i += 4 + (sz * ew + 1) // 2
                continue
            if op == 0x1A:                           # const-string      21c
                idx = struct.unpack_from("<H", d, insns_off + 2 * (i + 1))[0]
                if idx in perm:
                    struct.pack_into("<H", d, insns_off + 2 * (i + 1), perm[idx])
                    touched += 1
            elif op == 0x1B:                         # const-string/jumbo 31c
                idx = u32(d, insns_off + 2 * (i + 1))
                if idx in perm:
                    struct.pack_into("<I", d, insns_off + 2 * (i + 1), perm[idx])
                    touched += 1
            i += WIDTHS[op]
    return touched


def remap_id_tables(d, perm):
    """Remap non-code string index references (defensive; normally no-ops)."""
    touched = 0

    def fix(off):
        nonlocal touched
        idx = u32(d, off)
        if idx in perm:
            struct.pack_into("<I", d, off, perm[idx])
            touched += 1

    for size_off, off_off, stride, field in ((64, 68, 4, 0),     # type_ids.descriptor
                                             (72, 76, 12, 0),    # proto_ids.shorty
                                             (80, 84, 8, 4),     # field_ids.name
                                             (88, 92, 8, 4)):    # method_ids.name
        size = u32(d, size_off)
        off = u32(d, off_off)
        for i in range(size):
            fix(off + stride * i + field)
    cd_size = u32(d, 0x60)
    cd_off = u32(d, 0x64)
    for i in range(cd_size):                                     # class_defs.source_file
        sf = u32(d, cd_off + 32 * i + 16)
        if sf != 0xFFFFFFFF:
            fix(cd_off + 32 * i + 16)
    return touched


# ------------------------------------------------- encoded values (annotations)

def _fix_uleb(d, pos, perm, state):
    v, plen, _ = read_uleb128(d, pos)
    if v in perm:
        nb = enc_uleb128(perm[v])
        if len(nb) != plen:
            raise SystemExit("encoded reference at 0x%x would change length "
                             "(%d -> %d bytes)" % (pos, plen, len(nb)))
        d[pos:pos + plen] = nb
        state[0] += 1
    return v


def _fix_index(d, pos, width, perm, state):
    v = int.from_bytes(bytes(d[pos:pos + width]), "little")
    if v in perm:
        nv = perm[v]
        if nv >= (1 << (8 * width)):
            raise SystemExit("encoded reference at 0x%x does not fit in %d bytes"
                             % (pos, width))
        d[pos:pos + width] = nv.to_bytes(width, "little")
        state[0] += 1


def _walk_encoded_value(d, p, perm, state):
    """Advance past one encoded_value, remapping VALUE_STRING indices."""
    header = d[p]
    p += 1
    vt = header & 0x1F
    va = (header >> 5) & 0x7
    if vt in (0x00, 0x02, 0x03, 0x04, 0x06, 0x10, 0x11,
              0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B):
        # value_arg + 1 bytes, little endian; for the index types the stored
        # value is a *string index* only for VALUE_STRING (0x17).
        width = va + 1
        if vt == 0x17:
            _fix_index(d, p, width, perm, state)
        return p + width
    if vt == 0x1C:                           # VALUE_ARRAY
        size, _, p = read_uleb128(d, p)
        for _ in range(size):
            p = _walk_encoded_value(d, p, perm, state)
        return p
    if vt == 0x1D:                           # VALUE_ANNOTATION
        return _walk_encoded_annotation(d, p, perm, state)
    if vt in (0x1E, 0x1F):                   # VALUE_NULL / VALUE_BOOLEAN
        return p
    raise SystemExit("unknown encoded_value type 0x%02x at 0x%x" % (vt, p - 1))


def _walk_encoded_annotation(d, p, perm, state):
    _, _, p = read_uleb128(d, p)             # type_idx (a type, not a string idx)
    size, _, p = read_uleb128(d, p)
    for _ in range(size):
        _fix_uleb(d, p, perm, state)         # element name_idx
        _, plen, _ = read_uleb128(d, p)
        p += plen
        p = _walk_encoded_value(d, p, perm, state)
    return p


def _walk_encoded_array(d, off, perm, state):
    size, _, p = read_uleb128(d, off)
    for _ in range(size):
        p = _walk_encoded_value(d, p, perm, state)


def _walk_annotation_set(d, off, perm, state):
    size = u32(d, off)
    for i in range(size):
        aoff = u32(d, off + 4 + 4 * i)
        _walk_encoded_annotation(d, aoff + 1, perm, state)   # +1 visibility byte


def _walk_annotations_directory(d, off, perm, state):
    class_anno = u32(d, off)
    if class_anno:
        _walk_annotation_set(d, class_anno, perm, state)
    fs, ms, ps = u32(d, off + 4), u32(d, off + 8), u32(d, off + 12)
    p = off + 16
    for _ in range(fs + ms + ps):
        aoff = u32(d, p + 4)
        p += 8
        if aoff:
            _walk_annotation_set(d, aoff, perm, state)


def _map_section(d, type_code):
    """Return (size, offset) of a section from the dex map_list, or (0, 0)."""
    map_off = u32(d, 0x34)
    if not map_off:
        return 0, 0
    n = u32(d, map_off)
    for i in range(n):
        e = map_off + 4 + 12 * i
        if struct.unpack_from("<H", d, e)[0] == type_code:
            return u32(d, e + 4), u32(d, e + 8)
    return 0, 0


def remap_encoded(d, perm):
    """Remap string indices inside annotations, static values and call sites."""
    state = [0]
    cd_size = u32(d, 0x60)
    cd_off = u32(d, 0x64)
    for i in range(cd_size):
        base = cd_off + 32 * i
        anno_off = u32(d, base + 20)         # annotations_off
        if anno_off:
            _walk_annotations_directory(d, anno_off, perm, state)
        sv_off = u32(d, base + 28)           # static_values_off
        if sv_off:
            _walk_encoded_array(d, sv_off, perm, state)
    cs_size, cs_off = _map_section(d, 0x0007)   # TYPE_CALL_SITE_ID_ITEM
    for i in range(cs_size):
        item_off = u32(d, cs_off + 4 * i)
        if item_off:
            _walk_encoded_array(d, item_off, perm, state)
    return state[0]


# ------------------------------------------------------------------ the patch

def patch(d, mapping):
    ssize = u32(d, 56)               # string_ids_size
    soff = u32(d, 60)                # string_ids_off

    offs = [u32(d, soff + 4 * i) for i in range(ssize)]
    unique = sorted(set(offs))
    items = {o: read_string_data(d, o) for o in unique}

    region_start = unique[0]
    region_end = max(o + items[o][1] for o in unique)
    region_len = region_end - region_start

    mapping_b = {k.encode("utf-8"): v.encode("utf-8") for k, v in mapping.items()}

    # 1) rebuild the whole string_data region from its start, densely.
    final = {}
    blob = bytearray()
    new_off = {}
    for o in unique:
        payload = items[o][0]
        nb = mapping_b.get(payload)
        if nb is None:
            item = bytes(d[o:o + items[o][1]])
            final[o] = payload
        else:
            item = enc_uleb128(len(mutf8_units(nb))) + nb + b"\x00"
            final[o] = nb
        new_off[o] = region_start + len(blob)
        blob += item

    if len(blob) > region_len:
        raise SystemExit("string_data region would grow by %d bytes; refusing"
                         % (len(blob) - region_len))
    d[region_start:region_start + len(blob)] = blob
    if len(blob) < region_len:
        d[region_start + len(blob):region_end] = b"\x00" * (region_len - len(blob))

    off_for_content = {}
    for o in unique:
        off_for_content.setdefault(final[o], new_off[o])

    before = [items[o][0] for o in offs]
    after = [final[o] for o in offs]
    changed = [i for i in range(ssize) if before[i] != after[i]]
    if not changed:
        return 0, 0, None

    # 2) the pool was sorted before the edit and this key reproduces that order
    #    exactly, so a full re-sort is the minimal correct repair and yields the
    #    precise set of indices that move.
    order = sorted(range(ssize), key=lambda i: (sort_key(after[i]), i))

    # 3) rewrite string_ids in sorted order, collecting the indices that moved
    perm = {}
    for pos, i in enumerate(order):
        struct.pack_into("<I", d, soff + 4 * pos, off_for_content[after[i]])
        if pos != i:
            perm[i] = pos

    # 4) remap every reference to a moved index
    code_hits = remap_const_strings(d, perm)
    id_hits = remap_id_tables(d, perm)
    enc_hits = remap_encoded(d, perm)

    fix_header(d)
    return len(changed), code_hits, (ssize, len(perm), id_hits, enc_hits)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("dex")
    ap.add_argument("out")
    ap.add_argument("--map", action="append", default=[])
    ap.add_argument("--allow-id-refs", action="store_true",
                    help="permit non-code references to moved strings (verify the result)")
    args = ap.parse_args(argv[1:])

    d = bytearray(open(args.dex, "rb").read())
    if d[:4] != b"dex\n":
        raise SystemExit("not a dex: %s" % args.dex)

    mapping = {}
    for m in args.map:
        if "=" not in m:
            raise SystemExit("--map needs old=new, got %r" % m)
        k, v = m.split("=", 1)
        mapping[k] = v
    if not mapping:
        raise SystemExit("no --map given")

    changed, code_hits, info = patch(d, mapping)
    open(args.out, "wb").write(bytes(d))
    if not changed:
        print("no strings changed")
        return 0
    total, nmoved, id_hits, enc_hits = info
    print("strings replaced: %d" % changed)
    print("string_ids entries re-ordered: %d of %d" % (nmoved, total))
    print("const-string operands remapped: %d" % code_hits)
    print("id-table refs remapped: %d   encoded refs remapped: %d"
          % (id_hits, enc_hits))
    if (id_hits or enc_hits) and not getattr(args, "allow_id_refs", False):
        raise SystemExit("non-code references to moved strings were remapped; "
                         "re-run with --allow-id-refs after verifying the result")
    print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
