#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Point `const-string` operands at a different existing string.

Used to make a literal harmless while leaving the string pool (and therefore the
`string_ids` ordering) completely untouched: the old string stays in the pool,
unreferenced.

  dex_retarget_const.py in.dex out.dex --from "<old>" --to "<new>"

Every `const-string`/`const-string/jumbo` whose *resolved* value equals --from is
repointed to the (already present) string --to.  Fails if --to is not in the
pool, since adding a string would require re-sorting `string_ids`.
"""

import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dex_strings_sorted_patch import (  # noqa: E402
    WIDTHS, fix_header, iter_code_items, read_string_data, u32,
)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("dex")
    ap.add_argument("out")
    ap.add_argument("--from", dest="old", required=True)
    ap.add_argument("--to", dest="new", required=True)
    args = ap.parse_args(argv[1:])

    d = bytearray(open(args.dex, "rb").read())
    if d[:4] != b"dex\n":
        raise SystemExit("not a dex: %s" % args.dex)

    ssize = u32(d, 56)
    soff = u32(d, 60)
    idx_payload = {}
    content_to_idx = {}
    for i in range(ssize):
        payload, _ = read_string_data(d, u32(d, soff + 4 * i))
        idx_payload[i] = payload
        content_to_idx.setdefault(payload, i)

    old_b = args.old.encode("utf-8")
    new_b = args.new.encode("utf-8")
    if new_b not in content_to_idx:
        raise SystemExit("target string %r is not in the pool; refusing to add one" % args.new)
    new_idx = content_to_idx[new_b]

    hits = 0
    for insns_off, insns_size in iter_code_items(d):
        i = 0
        while i < insns_size:
            unit = struct.unpack_from("<H", d, insns_off + 2 * i)[0]
            op = unit & 0xFF
            if unit == 0x0100:
                size = struct.unpack_from("<H", d, insns_off + 2 * (i + 1))[0]
                i += 4 + size * 2
                continue
            if unit == 0x0200:
                size = struct.unpack_from("<H", d, insns_off + 2 * (i + 1))[0]
                i += 2 + size * 4
                continue
            if unit == 0x0300:
                ew = struct.unpack_from("<H", d, insns_off + 2 * (i + 1))[0]
                sz = u32(d, insns_off + 2 * (i + 2))
                i += 4 + (sz * ew + 1) // 2
                continue
            if op == 0x1A:
                op_off = insns_off + 2 * (i + 1)
                idx = struct.unpack_from("<H", d, op_off)[0]
                if idx_payload.get(idx) == old_b:
                    struct.pack_into("<H", d, op_off, new_idx)
                    hits += 1
            elif op == 0x1B:
                op_off = insns_off + 2 * (i + 1)
                idx = u32(d, op_off)
                if idx_payload.get(idx) == old_b:
                    struct.pack_into("<I", d, op_off, new_idx)
                    hits += 1
            i += WIDTHS[op]

    if hits == 0:
        raise SystemExit("no const-string resolved to %r" % args.old)
    fix_header(d)
    open(args.out, "wb").write(bytes(d))
    print("retargeted %d const-string operand(s): %r -> index %d" % (hits, args.old, new_idx))
    print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
