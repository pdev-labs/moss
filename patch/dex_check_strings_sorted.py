#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CI guard for a dex whose string pool was rewritten.

Fails the build if ART would reject the file (string_ids out of order) or if the
expected rebranded URLs are missing.

Usage: dex_check_strings_sorted.py file.dex
"""

import struct
import sys


def u32(d, o):
    return struct.unpack_from("<I", d, o)[0]


def mutf8_units(b):
    out = []
    i = 0
    while i < len(b):
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
            raise SystemExit("bad MUTF-8 at 0x%x" % i)
    return out


WANT = ["https://instagram.com/pdev_labs",
        "https://x.com/pdev_labs",
        "https://github.com/pdev-labs",
        "https://pdevlabs.me"]
GONE = ["https://instagram.com/sgnoogle",
        "https://x.com/sgnoogle",
        "https://youtube.com/@sgnoogle",
        "https://sgnoogle.com"]


def main(path):
    d = open(path, "rb").read()
    ssize = u32(d, 56)
    soff = u32(d, 60)
    strings = []
    for i in range(ssize):
        off = u32(d, soff + 4 * i)
        n = 0
        shift = 0
        p = off
        while True:
            b = d[p]
            p += 1
            n |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7
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
                raise SystemExit("bad MUTF-8 at 0x%x" % p)
        strings.append(d[start:p])

    def utf16(b):
        return mutf8_units(b)

    bad = [i for i in range(1, ssize) if utf16(strings[i]) < utf16(strings[i - 1])]
    if bad:
        raise SystemExit("string_ids NOT sorted; first bad index %d" % bad[0])

    ascii_strings = set()
    for b in strings:
        try:
            ascii_strings.add(b.decode("ascii"))
        except UnicodeDecodeError:
            pass

    missing = [w for w in WANT if w not in ascii_strings]
    stale = [g for g in GONE if g in ascii_strings]
    if missing:
        raise SystemExit("expected new URLs missing: %r" % missing)
    if stale:
        raise SystemExit("old URLs still present: %r" % stale)
    print("dex strings: %d entries, sorted OK; new URLs present, old URLs gone"
          % ssize)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
