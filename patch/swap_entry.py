#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Replace one entry's bytes inside an APK (same name, same compression method).

Used to drop in a recompiled drawable/asset without disturbing anything else.

Usage: swap_entry.py in.apk out.apk ENTRY FILE
"""
import sys
import zipfile


def main(in_apk, out_apk, entry, blob_path):
    blob = open(blob_path, "rb").read()
    with zipfile.ZipFile(in_apk) as z:
        infos = list(z.infolist())
        if entry not in [i.filename for i in infos]:
            raise SystemExit("entry not found: %s" % entry)
        with zipfile.ZipFile(out_apk, "w") as zo:
            for info in infos:
                data = blob if info.filename == entry else z.read(info.filename)
                zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                zi.compress_type = info.compress_type
                zi.external_attr = info.external_attr
                zo.writestr(zi, data)
    print("swapped %s (%d bytes) into %s" % (entry, len(blob), out_apk))


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit("usage: swap_entry.py in.apk out.apk ENTRY FILE")
    main(*sys.argv[1:])
