# Respiro premium-unlock — GitHub Actions build

Produces an installable, re-signed APK of **Respiro Minimal Launcher**
(`com.sgnoogle.respiro`, versionName 1.5 / versionCode 50) with the paid,
one-time-purchase features unlocked.

## What the build does

1. Extracts `classes.dex` from `base-original.apk` (input, read-only).
2. Applies **8 equal-length byte edits** with
   `patch/dex_patch_bytes.py --spec patch/patch_spec.json`.
   Nothing moves: no offset, try/catch block or debug pointer is invalidated, and
   the dex header SHA-1 signature + adler32 checksum are recomputed (signature first).
3. Repacks the APK, replacing `classes.dex` and dropping only the old
   `META-INF/*` signature entries (`patch/repack.py`).
4. `zipalign`s and signs with `apksigner` (v1+v2+v3).

## Why these edits

The app decides "premium" client-side (there is no entitlement server — the only
external hosts are `api.met.no` and `photon.komoot.io`). Entitlement is
`premium = premium_unlocked AND isOfficialSignature`, where:

| Flag | Where | Notes |
|---|---|---|
| `premium_unlocked` | DataStore key, read only in `q6.h1` | forced `true` (2 sites) |
| `widgets_unlocked` | DataStore key, read only in `q6.h1` | forced `true` (2 sites) |
| `isOfficialSignature` | `s6.h3.a()` case 10 vs hardcoded cert fingerprint in `r6.a` | forced `true` (2 sites) |

Forcing `isOfficialSignature` true (instead of replacing the fingerprint string)
keeps the build independent of the signing key and avoids a dex string-table
ordering violation.

`patch-report.json` (uploaded with the APK) records each matched site, the
polarity check and the new bytes.

## Keystore

`keystore/respiro.keystore`, alias `respiro`, store/key password `respiro123`.
It is committed so every workflow run produces the **same signature** (needed for
in-place updates). Do not reuse this key for anything of value.

## Notes / limits

- Verified mechanism: equal-length dex edits + class-table/verifier checks
  (`dex_check_verifier.py`, `dex_classdiff.py`) — 0 violations, class tables identical.
- `base-original.apk` was pulled from the user's device and is a third-party
  (re-signed) build; provenance is not the Play Store original.
- Premium features are local (themes/widgets tiles), so the client patch is
  sufficient; no server-minted content is involved.
