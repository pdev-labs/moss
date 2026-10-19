#!/usr/bin/env python3
"""Minimal deterministic APK repack: swap classes.dex, drop v1 signature entries.

Keeps every other entry as-is (name, compression method, order). Alignment is left
to `zipalign`, which is the authoritative tool for it.
"""
import sys
import zipfile

SRC_SIG_SUFFIXES = ('.SF', '.RSA', '.DSA', '.EC')


def is_sig_entry(name: str) -> bool:
    if not name.startswith('META-INF/'):
        return False
    upper = name.upper()
    if upper == 'META-INF/MANIFEST.MF':
        return True
    return upper.endswith(SRC_SIG_SUFFIXES)


def main(src, new_dex, out):
    with zipfile.ZipFile(src, 'r') as zin, zipfile.ZipFile(out, 'w') as zout:
        for info in zin.infolist():
            name = info.filename
            if is_sig_entry(name):
                continue
            if name == 'classes.dex':
                data = open(new_dex, 'rb').read()
            else:
                data = zin.read(name)
            out_info = zipfile.ZipInfo(name, date_time=info.date_time)
            out_info.compress_type = info.compress_type
            out_info.external_attr = info.external_attr
            zout.writestr(out_info, data)
    print('repacked: %s -> %s' % (src, out))


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit('usage: repack_simple.py <src.apk> <new_classes.dex> <out.apk>')
    main(sys.argv[1], sys.argv[2], sys.argv[3])
