# Moss — stable Android build

[![Build Moss stable APK](https://github.com/pdev-labs/moss/actions/workflows/build.yml/badge.svg)](https://github.com/pdev-labs/moss/actions/workflows/build.yml)
[![Latest release](https://img.shields.io/github/v/release/pdev-labs/moss?display_name=tag&sort=semver)](https://github.com/pdev-labs/moss/releases/latest)
[![License: none](https://img.shields.io/badge/license-not%20specified-lightgrey)](#license-and-legal)

**Moss** is an unofficial, re-signed Android build of the **Respiro Minimal
Launcher** (`com.sgnoogle.respiro`, versionName `1.5`, versionCode `50`). It keeps
the launcher's features, unlocks the client-side premium/widget entitlements,
removes the premium promotion tile, removes an injected third-party ad toast, and
rebrands the visible app identity to **Moss** (`org.moss.app`).

The APK is rebuilt from `base-original.apk` by a deterministic GitHub Actions
pipeline in this repository. The current stable release is **v1.5**, asset
[`moss-stable.apk`](https://github.com/pdev-labs/moss/releases/download/v1.5/moss-stable.apk).

> **This is not an official Respiro release.** It is not affiliated with,
> endorsed by, or supported by the original developer. The original application
> and its resources remain the property of their respective owners. Read
> [License and legal](#license-and-legal) before downloading or redistributing.

---

## Table of contents

- [At a glance](#at-a-glance)
- [Download](#download)
- [Verify the download](#verify-the-download)
- [Install, update, and uninstall](#install-update-and-uninstall)
- [What is changed](#what-is-changed)
- [What is intentionally not changed](#what-is-intentionally-not-changed)
- [How the build works](#how-the-build-works)
- [The dex patches in detail](#the-dex-patches-in-detail)
- [String-pool rewriting and ART constraints](#string-pool-rewriting-and-art-constraints)
- [Manifest and resource rebranding](#manifest-and-resource-rebranding)
- [Repository layout](#repository-layout)
- [Build it yourself](#build-it-yourself)
- [Verification and test evidence](#verification-and-test-evidence)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Keystore and signing](#keystore-and-signing)
- [Security notes](#security-notes)
- [Known limitations](#known-limitations)
- [Changelog](#changelog)
- [Credits](#credits)
- [License and legal](#license-and-legal)

---

## At a glance

| Item | Value |
|---|---|
| App name | **Moss** |
| Package name | `org.moss.app` |
| Base app | Respiro Minimal Launcher `com.sgnoogle.respiro` |
| Base version | `1.5` (versionCode `50`) |
| Output version | `1.5` (versionCode `50`) |
| Min SDK | 26 (Android 8.0) |
| Target / compile SDK | 36 (Android 16) |
| Architectures | `arm64-v8a`, `armeabi-v7a`, `x86`, `x86_64` |
| Release asset | `moss-stable.apk` |
| Release SHA-256 | `17c834f3f73cfb8c9a3c29992da546ab262130663af93b5a01b8e891dad1edf7` |
| Release size | 3,055,564 bytes |
| Signing certificate SHA-256 | `FB:DF:24:68:61:5A:46:87:7A:32:5B:3B:44:06:5B:09:56:ED:FC:1F:5B:E1:D5:E8:32:8E:03:AC:88:C8:AF:40` |
| Base APK SHA-256 | `9ad5b536088274924626198ed79dab0fbad43b04fddab660775efa2e6c55f84f` |
| Root required | No |
| Signature scheme | APK Signature Scheme v1 + v2 + v3 |
| Update channel | Manual only; no in-app updater |

The name **stable** means this is the long-lived, reproducible channel of this
personal build. It does not imply support from the original developer.

---

## Download

Get the APK from the **Releases** page:

- Direct link:
  <https://github.com/pdev-labs/moss/releases/download/v1.5/moss-stable.apk>
- Release page:
  <https://github.com/pdev-labs/moss/releases/tag/v1.5>

The release also documents the SHA-256 of the asset. Always verify it before
installing.

The GitHub Actions artifact for a given commit is named **`moss-stable-apk`** and
contains:

- `moss-stable.apk` — the signed, aligned APK.
- `work/patch-report.json` — a machine-readable record of every dex patch site,
  including the old and new instruction bytes and verifier checks.

---

## Verify the download

### SHA-256

```bash
# Linux
sha256sum moss-stable.apk

# macOS
shasum -a 256 moss-stable.apk

# Windows PowerShell
Get-FileHash .\moss-stable.apk -Algorithm SHA256
```

Expected for the v1.5 stable asset:

```text
17c834f3f73cfb8c9a3c29992da546ab262130663af93b5a01b8e891dad1edf7
```

A local rebuild can differ in the v3 signature block while keeping the same
`classes.dex`, resources, and manifest. Compare `patch-report.json` and the dex
hashes from the workflow log when you need to compare builds rather than whole
APK bytes.

### Signing certificate

With Android build-tools installed:

```bash
apksigner verify --print-certs moss-stable.apk
```

Expected certificate SHA-256 digest:

```text
FB:DF:24:68:61:5A:46:87:7A:32:5B:3B:44:06:5B:09:56:ED:FC:1F:5B:E1:D5:E8:32:8E:03:AC:88:C8:AF:40
```

The certificate subject is:

```text
CN=Respiro Rebuild, O=Local, C=US
```

This is a throwaway rebuild key committed only so repeated builds share one
signature. See [Keystore and signing](#keystore-and-signing).

---

## Install, update, and uninstall

### Requirements

- Android 8.0 (API 26) or newer.
- An ARM, ARM64, x86, or x86_64 device/emulator. The app ships the
  `androidx.graphics.path` native library for all four ABIs.
- “Install unknown apps” permission for whichever app opens the APK.

### Install over ADB

```bash
adb install -r moss-stable.apk
```

`-r` reinstalls while keeping app data. On a fresh device the package is new, so
data is created empty.

Launch it from the home screen, or:

```bash
adb shell monkey -p org.moss.app -c android.intent.category.LAUNCHER 1
```

### Install from the device

1. Download `moss-stable.apk`.
2. Open it from Files/Downloads.
3. Allow the source app to install unknown apps when prompted.
4. Confirm the install and open **Moss**.

### Updating

Future `moss-stable` builds use the same committed keystore, so they can be
installed over an existing `org.moss.app` installation:

```bash
adb install -r moss-stable.apk
```

Do **not** try to install this over the original `com.sgnoogle.respiro` package.
Android treats them as two different apps: they can coexist, but they do not
share data or settings.

### Uninstall

```bash
adb uninstall org.moss.app
```

Uninstalling removes the app's private data, including the local premium flags
and launcher preferences.

---

## What is changed

### User-visible changes

| Change | Detail |
|---|---|
| App name | **Moss** instead of Respiro |
| Package name | `org.moss.app` instead of `com.sgnoogle.respiro` |
| Premium entitlement | `premium_unlocked` is forced true in the read path |
| Widget entitlement | `widgets_unlocked` is forced true in the read path |
| Signature check | The client-side “official signature” gate is forced true |
| Premium tile | The settings promotion tile is not drawn |
| Third-party ad toast | The injected `modyolo.com` toast is no longer called |
| “Leave a review” | Opens a new issue on this repository instead of the Play Store |
| Author/brand copy | `Francesco` → `pdev-labs` in every locale's app copy |
| Social links | Instagram/X → `pdev_labs`; YouTube → GitHub; site → `pdevlabs.me` |
| Contact email | `pdev.labs+moss@gmail.com` |
| HTTP User-Agent | `MossLauncher/1.5` |
| Boot/premium keys | `respiro_boot` → `moss_boot`, `respiro_premium` → `moss_premium` |
| Privacy/Terms footer | Labels blanked and separator retargeted, so the footer renders empty |
| YouTube icon | Replaced with a GitHub mark (compiled vector drawable) |

### What the premium unlock actually does

The app has **no entitlement server**. Its only external hosts are
`api.met.no` (weather) and `photon.komoot.io` (geocoding). Entitlement is
evaluated entirely on-device as:

```text
premium = premium_unlocked AND isOfficialSignature
```

`premium_unlocked` and `widgets_unlocked` are boolean values stored in AndroidX
DataStore. `isOfficialSignature` compares the installed APK's signing
certificate with a fingerprint embedded in the app.

This build changes the **read paths** so both flags resolve `true` and the
signature gate resolves `true`, instead of replacing the embedded fingerprint or
shipping a matching private key. That keeps the patch independent of the signing
key and avoids changing the dex string table for a certificate.

The premium features are local UI features (themes/widgets tiles), so a
client-side patch is sufficient. No paid server-side content is unlocked.

---

## What is intentionally not changed

These are deliberate, not oversights:

| Kept | Why |
|---|---|
| Java package/class names (`com.sgnoogle.respiro.*`) | They must match the compiled dex. Only the manifest `package` and package-derived authorities are renamed. |
| Lowercase DataStore keys | They are existing on-disk identifiers; changing them would orphan settings. |
| The word “respiro” in Italian/Spanish/Portuguese copy | It means “breath” in those languages and is ordinary copy, not branding. |
| The base APK's `TryRoom` / `SavesRestoringPortable` classes | They belong to the input repack. They are not needed by this build; removing them would require larger structural dex edits. See [Security notes](#security-notes). |
| Most of the original app's code and resources | This is a patch-and-repack project, not a source fork. |
| `versionCode 50` / `versionName 1.5` | The build tracks the base release; it is not a new upstream version. |

---

## How the build works

The workflow is `.github/workflows/build.yml`. It runs on every push to `main`
and on manual dispatch. It needs no secrets; everything comes from the repository.

```text
base-original.apk
      │
      ├─ extract classes.dex
      │
      ├─ dex_patch_bytes.py ............ 12 equal-length instruction patches
      │                                   (premium/widget/signature gates,
      │                                    ad toast, premium tile, review URL)
      │
      ├─ dex_strings_sorted_patch.py ... URL/author/UA/key renames; rebuilds the
      │                                   string_data region, re-sorts string_ids,
      │                                   remaps every moved reference
      │
      ├─ dex_retarget_const.py ......... "·" → "" (empty footer separator)
      │
      ├─ dex_check_strings_sorted.py ... CI guard: strict ordering, no duplicates,
      │                                   expected strings present/stale strings gone
      │
      ├─ repack_simple.py .............. replace classes.dex, drop old META-INF
      │                                   signature entries, preserve entry order
      │
      ├─ rebrand_axml.py ............... package org.moss.app + label Moss +
      │                                   startup authority/permission rename
      │
      ├─ rebrand_strings.py ............ resources.arsc: brand/legal string edits
      │
      ├─ swap_entry.py ................. replace the YouTube vector with GitHub
      │
      ├─ zipalign -p -f 4 .............. page-align uncompressed entries
      │
      └─ apksigner sign ................ v1 + v2 + v3, then verify + SHA-256
```

### Step details

1. **Checkout.** The base APK, patch scripts, and keystore are all in the repo.
2. **JDK.** Temurin 17 is installed for `apksigner`.
3. **Build-tools discovery.** The workflow finds the newest installed
   `build-tools` directory, installing `build-tools;34.0.0` if none is present.
4. **Dex extraction.** `classes.dex` is extracted from `base-original.apk` into
   `work/`. The base APK itself is never modified.
5. **Equal-length patches.** `patch/dex_patch_bytes.py` applies
   `patch/patch_spec.json` and writes `work/patch-report.json`. Every replacement
   is the same byte length as the instruction it replaces, so no code offset,
   branch displacement, try/catch range, or debug pointer moves.
6. **String renames.** `patch/dex_strings_sorted_patch.py` rewrites exact strings
   and repairs the dex string table (see
   [String-pool rewriting and ART constraints](#string-pool-rewriting-and-art-constraints)).
7. **Footer cleanup.** `patch/dex_retarget_const.py` points the `"·"` separator
   at the pool's existing empty string, so the Privacy/Terms footer renders
   empty without adding a string or re-sorting the pool.
8. **Guard.** `patch/dex_check_strings_sorted.py` fails the build if ART would
   reject the dex, if a duplicate `string_ids` entry exists, or if any expected
   rebranded string is missing or any stale string remains.
9. **Repack.** `patch/repack_simple.py` keeps every entry in its original order,
   swaps only `classes.dex`, and removes `META-INF/MANIFEST.MF` plus
   `.SF`/`.RSA`/`.DSA`/`.EC` v1 signature files. It does not reuse the old
   signature block.
10. **Manifest rebrand.** `patch/rebrand_axml.py` edits the binary AXML string
    pool in place: `package` becomes `org.moss.app`, `android:label` becomes the
    literal `Moss`, and the package-derived AndroidX startup authority and
    dynamic-receiver permission are renamed to avoid
    `INSTALL_FAILED_CONFLICTING_PROVIDER` while the original app is installed.
11. **Resource rebrand.** `patch/rebrand_strings.py` re-encodes the global
    string pool in `resources.arsc` (all locales): `Respiro` → `Moss`,
    `Francesco` → `pdev-labs`, and the Privacy/Terms labels → empty strings.
12. **Icon swap.** `patch/swap_entry.py` replaces
    `res/drawable/ic_social_youtube.xml` with a compiled GitHub mark.
13. **Align and sign.** `zipalign -p 4` aligns uncompressed entries, then
    `apksigner` signs with v1+v2+v3 and verifies with `--min-sdk-version 26
    --max-sdk-version 36`.
14. **Publish artifact.** The signed APK and `patch-report.json` are uploaded as
    the `moss-stable-apk` artifact.

---

## The dex patches in detail

`patch/patch_spec.json` currently contains **12** patches. The report writes one
entry per patch with the class, method, descriptor, method/code offsets, matched
instruction, neighbours, replacement bytes, post-decode sanity check, and
verifier edges.

### Entitlement flags — three patches per flag

The read site is the flow-mapping coroutine `Lq6/h1;->g`. For each of
`widgets_unlocked` and `premium_unlocked`, three equal-length edits are used:

| Patch | Effect |
|---|---|
| `*_unlocked_force_true` | Replaces the null-check branch with `const/4 v1, 1` (4 bytes), so the value is always true. |
| `*_unlocked_del_nullcheck` | NOPs the `Boolean.booleanValue()` call that the removed branch used to guard (6 bytes). |
| `*_unlocked_del_moveresult` | NOPs the now-unpaired `move-result` (2 bytes), keeping the method verifier-legal. |

The three edits are coupled: removing the branch alone would dereference a
possibly-null `Boolean`, and removing the invoke alone would leave an illegal
`move-result`. The spec's `expect_next` assertions pin the polarity of the match
so the wrong branch cannot be patched silently.

### Signature gate — two patches

`Ls6/h3;->a()` (case 10) returns whether the installed signature matches the
hardcoded fingerprint. The method has a cached path and a compute path; both
converge on `Boolean.valueOf(v0)`.

| Patch | Effect |
|---|---|
| `sigcheck_cached_path_true` | Replaces the cached-path `move-result v0` with `const/4 v0, 1`. |
| `sigcheck_compute_path_true` | Replaces the compute-path `move v0, v1` with `const/4 v0, 1`. |

### UI / third-party cleanups

| Patch | Effect |
|---|---|
| `remove_modyolo_toast_call` | NOPs the injected `_showModYoloToast()` invoke at the top of `MainActivity.onCreate`, removing the `modyolo.com` toast. |
| `remove_premium_tile` | Returns immediately from `Ls6/hj;->K`, the “You're a premium user” settings tile renderer. |
| `review_no_pkg_append_1` | NOPs `StringBuilder.append(packageName)` on the browser branch of the “Leave a review” URL builder. |
| `review_no_pkg_append_2` | Same for the fallback branch, which is reached only when no browser is available. |

The review URLs are deliberately two distinct strings:

```text
https://github.com/pdev-labs/moss/issues/new
https://github.com/pdev-labs/moss/issues/new?
```

ART requires **strictly increasing** `string_ids`; two equal entries make dexopt
fail with `Out-of-order string_ids`. The trailing `?` on the never-taken fallback
keeps the two entries distinct. The patcher also aborts if two replacements
would become equal.

### Why equal-length edits?

Rebuilding a method body with baksmali/smali moves code and requires repairing
branches, try/catch ranges, debug info, and sometimes register allocation. The
in-place approach avoids all of that. The cost is that only instructions of the
same width can be substituted. `dex_patch_bytes.py` therefore checks:

- the replacement decodes to a valid instruction sequence of exactly the same
  length;
- an optional `expect_next` instruction matches (polarity check);
- a branch target is not a `move-result*` that would bypass its producing invoke;
- the whole method still decodes cleanly after the edit;
- the dex header SHA-1 signature and Adler-32 checksum are recomputed, signature
  first.

---

## String-pool rewriting and ART constraints

Renaming URLs and brand strings is not as simple as finding bytes in
`classes.dex`. Three ART rules matter:

1. **`string_ids` must be sorted** by string content in UTF-16 code-unit order.
   ART otherwise rejects the dex with
   `Out-of-order string_ids: 'A' then 'B'`.
2. **`string_ids` must be strictly increasing.** A duplicate makes dexopt fail
   even though baksmali and some verifiers accept it.
3. **`string_data_item` offsets are absolute.** A replacement that changes length
   cannot simply be written over the old bytes.

`patch/dex_strings_sorted_patch.py` therefore:

- rebuilds the entire `string_data` region densely, requiring net growth ≤ 0;
- re-sorts `string_ids` in place (the region is fixed-size, so the file size does
  not change);
- remaps every reference to a moved index:
  - type/prototype/field/method name indices,
  - class source-file indices,
  - `const-string` and `const-string/jumbo` operands,
  - annotation element `name_idx` values and `VALUE_STRING` encoded values,
- recomputes the header checksum and signature.

`--allow-id-refs` permits replacements that also move ids used by annotations,
which is required for the broad `Respiro` → `Moss` rename. The CI guard runs a
full consistency check on the final dex, and a local baksmali diff of patched vs
original is used during development to confirm only intended literals changed.

### Rebrand map applied to `classes.dex`

```text
https://instagram.com/sgnoogle  -> https://instagram.com/pdev_labs
https://x.com/sgnoogle          -> https://x.com/pdev_labs
https://youtube.com/@sgnoogle   -> https://github.com/pdev-labs
https://sgnoogle.com            -> https://pdevlabs.me
RespiroLauncher/1.5 francesco.sgnaolin+respiro@gmail.com
                                -> MossLauncher/1.5 pdev.labs+moss@gmail.com
mailto:francesco.sgnaolin+respiro@gmail.com
                                -> mailto:pdev.labs+moss@gmail.com
Respiro                         -> Moss
RespiroLauncher                 -> MossLauncher
respiro_boot                    -> moss_boot
respiro_premium                 -> moss_premium
https://play.google.com/store/apps/details?id=
                                -> https://github.com/pdev-labs/moss/issues/new?
market://details?id=            -> https://github.com/pdev-labs/moss/issues/new
```

The two review prefixes map to different strings on purpose (see the duplicate
`string_ids` note above).

---

## Manifest and resource rebranding

### Why not a full apktool rebuild?

`apktool b` on this R8/Compose app is slow and fragile. The build needs only a
few edits, so it edits the binary formats directly:

- **AXML** (`AndroidManifest.xml`): a chunked string pool plus XML nodes. The
  script re-encodes the pool, keeps string indices stable, flips the application
  label from a resource reference to a literal, and copies the node chunks
  verbatim. Node attributes reference strings by index, never by absolute offset,
  so moving the pool is safe. The file-size header is patched to match.
- **ARSC** (`resources.arsc`): one global string pool for all locales. The script
  re-encodes the pool, patches the table size, and pads to a 4-byte boundary
  (aapt/Android reject a non-aligned table).

### Package-derived names

Only the manifest `package` and these derived identifiers change:

```text
com.sgnoogle.respiro.androidx-startup
    -> org.moss.app.androidx-startup
com.sgnoogle.respiro.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION
    -> org.moss.app.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION
```

Java class names such as `com.sgnoogle.respiro.MainActivity` and
`com.sgnoogle.respiro.LauncherApp` stay unchanged because they must resolve to
the compiled dex. The launcher component is therefore:

```text
org.moss.app/com.sgnoogle.respiro.MainActivity
```

If the startup provider authority were not renamed, installing Moss alongside
the original Respiro would fail with
`INSTALL_FAILED_CONFLICTING_PROVIDER`.

### Settings crash fix

An early GitHub-mark replacement was compiled with `aapt2 link` without a
`minSdkVersion`, which produced a versioned-vector stub. The base entry had no
`viewportWidth`, and opening Settings crashed with:

```text
XmlPullParserException: <VectorGraphic> tag requires viewportWidth > 0
```

The fix was to recompile the vector with `minSdk 26` and
`--no-version-vectors`, so the base `res/drawable/ic_social_youtube.xml` keeps
`height`, `width`, `viewportWidth`, `viewportHeight`, `fillColor`, and
`pathData`.

---

## Repository layout

```text
.
├── .github/workflows/build.yml   GitHub Actions build
├── base-original.apk             input APK (read-only; ~3.0 MB)
├── keystore/
│   └── respiro.keystore          throwaway rebuild key (see warning)
├── patch/
│   ├── assets/
│   │   └── ic_social_youtube.xml compiled GitHub vector
│   ├── dex_patch_bytes.py        equal-length dex patcher + verifier checks
│   ├── dexutil.py                dependency-free dex parser / instruction decoder
│   ├── dex_strings_sorted_patch.py
│   │                             string replacement + string_ids re-sort/remap
│   ├── dex_retarget_const.py     repoint const-string at an existing string
│   ├── dex_check_strings_sorted.py
│   │                             CI guard for ordering/duplicates/expected strings
│   ├── patch_spec.json           declarative patch list (12 entries)
│   ├── rebrand_axml.py           binary manifest package/label editor
│   ├── rebrand_strings.py        resources.arsc string-pool editor
│   ├── repack.py                 full repack/sign helper (not used by CI)
│   ├── repack_simple.py          minimal deterministic repack used by CI
│   └── swap_entry.py             replace one zip entry
├── README.md
└── .gitignore
```

`work/` is generated and ignored. `patch-report.json` is produced inside `work/`
and uploaded with the artifact.

---

## Build it yourself

### Prerequisites

- Python 3.9+ (standard library only; no pip packages).
- JDK 17+.
- Android SDK build-tools with `zipalign` and `apksigner` (`34.0.0` is used in CI).
- A Linux/macOS shell. Windows works with WSL; the scripts themselves are
  POSIX-friendly Python.

### Reproduce the CI build

```bash
git clone https://github.com/pdev-labs/moss.git
cd moss
mkdir -p work

python3 - <<'PY'
import zipfile
zipfile.ZipFile('base-original.apk').extract('classes.dex', 'work')
PY

python3 patch/dex_patch_bytes.py work/classes.dex \
  --spec patch/patch_spec.json \
  -o work/classes-final.dex \
  --report work/patch-report.json

python3 patch/dex_strings_sorted_patch.py work/classes-final.dex work/classes-strings.dex \
  --map "https://instagram.com/sgnoogle=https://instagram.com/pdev_labs" \
  --map "https://x.com/sgnoogle=https://x.com/pdev_labs" \
  --map "https://youtube.com/@sgnoogle=https://github.com/pdev-labs" \
  --map "https://sgnoogle.com=https://pdevlabs.me" \
  --map "RespiroLauncher/1.5 francesco.sgnaolin+respiro@gmail.com=MossLauncher/1.5 pdev.labs+moss@gmail.com" \
  --map "mailto:francesco.sgnaolin+respiro@gmail.com=mailto:pdev.labs+moss@gmail.com" \
  --map "Respiro=Moss" \
  --map "RespiroLauncher=MossLauncher" \
  --map "respiro_boot=moss_boot" \
  --map "respiro_premium=moss_premium" \
  --map "https://play.google.com/store/apps/details?id==>https://github.com/pdev-labs/moss/issues/new?" \
  --map "market://details?id==>https://github.com/pdev-labs/moss/issues/new" \
  --allow-id-refs

python3 patch/dex_retarget_const.py work/classes-strings.dex work/classes-strings2.dex \
  --from "·" --to ""

python3 patch/dex_check_strings_sorted.py work/classes-strings2.dex
python3 patch/repack_simple.py base-original.apk work/classes-strings2.dex work/repacked.apk

python3 patch/rebrand_axml.py work/repacked.apk work/rebranded.apk \
  --package org.moss.app --label Moss

python3 patch/rebrand_strings.py work/rebranded.apk work/rebranded2.apk \
  --old Respiro --new Moss --old Francesco --new pdev-labs \
  --old "Privacy policy" --new "" --old "Terms of service" --new ""

python3 patch/swap_entry.py work/rebranded2.apk work/rebranded3.apk \
  res/drawable/ic_social_youtube.xml patch/assets/ic_social_youtube.xml

zipalign -p -f 4 work/rebranded3.apk work/aligned.apk
apksigner sign \
  --ks keystore/respiro.keystore \
  --ks-pass pass:respiro123 \
  --key-pass pass:respiro123 \
  --ks-key-alias respiro \
  --v1-signing-enabled true --v2-signing-enabled true --v3-signing-enabled true \
  --out moss-stable.apk work/aligned.apk

apksigner verify --print-certs --verbose \
  --min-sdk-version 26 --max-sdk-version 36 moss-stable.apk
sha256sum moss-stable.apk
```

Set `PATH` to include the build-tools directory, or replace `zipalign` /
`apksigner` with absolute paths.

### Dry-run a patch

`dex_patch_bytes.py` has a `--dry-run` mode that prints matches, neighbours,
verifier verdict, and the predicted byte diff without writing:

```bash
python3 patch/dex_patch_bytes.py base-original.apk \
  --spec patch/patch_spec.json --dry-run
```

---

## Verification and test evidence

The build is checked at several levels:

| Layer | Check |
|---|---|
| Patch matching | Exact method/descriptor, instruction kind, optional `expect_next` polarity assertion. |
| Decode | The patched method is decoded end-to-end; instruction count and boundaries must remain sane. |
| Verifier | No branch may target a `move-result*` without its producing invoke; reported as `verifier_edges: 0`. |
| Dex header | SHA-1 signature and Adler-32 checksum recomputed, signature first. |
| String table | Strictly increasing `string_ids`, no duplicates, expected strings present, stale strings absent. |
| Repack | No duplicate zip entries; old `META-INF` signature files removed; `resources.arsc` stays `STORED`. |
| Alignment | `zipalign -c -p 4` passes. |
| Signature | `apksigner verify` passes for v1/v2/v3 and prints the expected certificate. |
| Device | Installed on a Vivo V2437 (Android 16, arm64-v8a, unrooted); app launches, Settings opens, premium state persists across cold start. |

The CI rebuild for commit `f0262fe` (GitHub Actions run `39262685376`)
reproduced the v1.5 release asset byte-for-byte: both are 3,055,564 bytes with
SHA-256 `17c834f3f73cfb8c9a3c29992da546ab262130663af93b5a01b8e891dad1edf7`.

Historical on-device checks for this build line:

- Fresh install as `org.moss.app` succeeds alongside the original app.
- System “App info” shows the name **Moss**.
- Settings opens without crashing and “Advanced features” is available; the
  “You're a premium user” promotion tile is gone.
- No `modyolo.com` toast on cold or warm start.
- No `Out-of-order string_ids`, `Failure to verify dex file`, or
  `FATAL EXCEPTION` in logcat.
- The on-device `base.apk` SHA-256 matches the release asset.

Screenshots and UI dumps used during verification are kept outside this
repository (they contain device-specific state).

---

## Troubleshooting

### `INSTALL_FAILED_CONFLICTING_PROVIDER`

You are installing a build that did not rename the AndroidX startup provider
authority. Use the current `moss-stable.apk`; the manifest rebrand step handles
`org.moss.app.androidx-startup`.

### `INSTALL_FAILED_UPDATE_INCOMPATIBLE` / signature mismatch

An existing `org.moss.app` install was signed with a different key. Uninstall the
old copy first:

```bash
adb uninstall org.moss.app
adb install moss-stable.apk
```

### `Out-of-order string_ids` or `Failure to verify dex file`

The dex string table is invalid. This is what the `dex_check_strings_sorted.py`
CI guard prevents. Rebuild from a clean checkout and do not hand-edit the dex.

### `VerifyError` after a patch

A branch probably targets a `move-result*` whose invoke was removed, or the
replacement changed instruction width. Run the patcher with `--dry-run` and check
the `verifier_edges` / `post_decode_clean` fields.

### Settings crashes with `<VectorGraphic> tag requires viewportWidth > 0`

The GitHub vector was compiled as a versioned-vector stub. Recompile with
`minSdk 26` and `--no-version-vectors`.

### App installs but does not appear in the launcher

Some launchers cache their app list. Reboot, or check:

```bash
adb shell pm list packages | grep org.moss.app
adb shell cmd package resolve-activity --brief org.moss.app
```

### Play Protect warning

Android may warn about an unknown developer or a sideloaded app. That is expected
for a self-signed build. Only proceed if you verified the SHA-256 and trust the
source.

### Weather or geocoding does not work

The app still uses `api.met.no` and `photon.komoot.io`. Check network access and
the device's location permission. This build does not proxy or modify those
requests.

---

## FAQ

**Does this require root?**
No. The base app is a normal dex app with one small native library. Everything
here is client-side patching and re-signing.

**Does it work offline?**
The launcher itself does. Weather and geocoding need network access.

**Will I get app updates?**
No. There is no in-app updater and no Play Store listing. Watch this repository's
Releases or build it yourself.

**Does it keep my original Respiro settings?**
No. `org.moss.app` is a separate package. Android does not share private data
between packages. A fresh install starts with empty preferences.

**Why is the version still 1.5 / versionCode 50?**
The build tracks the base release. Changing `versionCode` would imply a new
upstream version and complicate in-place updates.

**Why not remove all `com.sgnoogle.respiro` strings?**
Class names and some on-disk identifiers must stay stable. Removing them would
require structural dex edits or break existing data. The OS-visible identity is
what changes.

**Is the premium unlock server-side?**
No. The app has no entitlement server. The unlock is local UI state plus a local
signature check.

**Can I use my own signing key?**
Yes. Change the `apksigner sign` arguments or replace `keystore/respiro.keystore`.
If you publish builds, keep one key so users can update in place. Do not reuse
the committed throwaway key for anything else.

**Why is the repo public if it ships a modified APK?**
The repository owner chose to publish the build and its patch scripts. Read the
legal notice below; publishing a modified third-party APK may violate the
original app's license or local law.

---

## Keystore and signing

`keystore/respiro.keystore` is committed so every CI run produces the **same
signature**, which is what allows in-place updates of `org.moss.app`. It is a
throwaway local key:

```text
alias:    respiro
store:    respiro123
key:      respiro123
subject:  CN=Respiro Rebuild, O=Local, C=US
```

**Do not reuse this key for anything of value.** It is public. Anyone can sign an
APK that updates an existing Moss install, so treat the signature as an
identity for this hobby build, not as a security guarantee.

The certificate is valid until 2059. The build uses APK Signature Scheme v1, v2,
and v3. `apksigner verify --print-certs` should show the SHA-256 fingerprint in
[At a glance](#at-a-glance).

---

## Security notes

- **Input provenance.** `base-original.apk` was pulled from a user device and is
  a third-party re-signed build, not a Play Store original. Its SHA-256 is
  recorded above. Treat the input as untrusted.
- **Modyolo layer.** The input contains a mod layer: an injected
  `_showModYoloToast()` ad call, `TryRoom` (an ApkSignatureKillerEx-style
  signature-spoofing helper), and `SavesRestoringPortable` (a stub that can
  decrypt `assets/data.save` into the app's DataStore). This build neutralizes
  the ad toast and does not rely on the signature-spoofing helper, but the
  classes remain in the APK because removing them would require larger
  structural edits. If you need a fully clean build, that is the next project.
- **Network.** The app's own external endpoints are `api.met.no` and
  `photon.komoot.io`. The base layer may contain additional third-party code;
  inspect it if that matters to you.
- **No secrets.** The only credential in the repo is the throwaway signing
  keystore password above. It is not a secret.
- **Supply chain.** Builds are produced by GitHub Actions from the checked-in
  scripts. If you install a release asset, verify its SHA-256 and certificate.
- **Sandboxing.** For high-risk use, install in a secondary profile or emulator.

---

## Known limitations

- No automatic updates, no Play Store listing, no F-Droid metadata.
- The app's Java package/class names still read `com.sgnoogle.respiro`; only the
  install identity and visible brand are Moss.
- A few internal identifiers (lowercase DataStore keys, the `respiro` word in
  Italian/Spanish/Portuguese copy) are intentionally unchanged.
- The `TryRoom` / `SavesRestoringPortable` classes from the input repack remain.
- The `base-original.apk` is a third-party build; its exact provenance is not
  independently verified.
- Reproducibility is “same inputs, same scripts, same key”; local build-tools
  versions can change the signature block bytes. Compare dex/resource hashes, not
  only whole-APK hashes.
- The release asset is a historical build; a fresh CI run may produce a different
  v3 signature block while keeping the same patched content.

---

## Changelog

### v1.5 — stable

- Rebuilt from Respiro Minimal Launcher 1.5 (versionCode 50).
- Premium and widgets entitlements forced true in the local read path.
- Client-side official-signature gate forced true.
- Premium promotion tile removed.
- Modyolo `modyolo.com` ad toast removed.
- Rebranded to **Moss** / `org.moss.app`.
- Author copy, social links, email, User-Agent, boot/premium keys rebranded.
- Privacy/Terms footer removed.
- YouTube social icon replaced with a GitHub mark.
- “Leave a review” opens a new GitHub issue on this repository.
- Settings `VectorGraphic` viewport crash fixed.
- CI guard for strict `string_ids` ordering and duplicates added.
- Build output/artifact/release asset renamed to `moss-stable.apk` /
  `moss-stable-apk`.

Earlier development milestones (private build line):

- Initial 8-patch premium unlock.
- Modyolo toast removal.
- Moss manifest/package rebrand.
- Author rebrand and social-link rewrite.
- Resource-string scrub and footer removal.
- Review-link redirect to GitHub.

---

## Credits

- Original app: **Respiro Minimal Launcher** by its respective developer. All
  original code, artwork, and resources remain theirs.
- Rebuild pipeline, dex tooling, and rebrand scripts: **pdev-labs**.
- The dex parser/patcher design was informed by the Android dex format and ART
  verifier behavior; no third-party Python packages are required.

If you find the original app useful, consider supporting its developer.

---

## License and legal

**No license is granted for the original application or its resources.** This
repository contains a modified, re-signed build of a third-party commercial app
plus scripts that perform the modification. The scripts are published for
personal interoperability, research, and preservation. They are not a grant of
rights to the original app.

This project is **unofficial** and is not affiliated with, endorsed by, or
supported by the original developer. “Respiro” and related marks belong to their
owners. “Moss” is used here only as the name of this personal rebuild.

Downloading, installing, or redistributing a modified APK may violate the
original app's license, Google Play terms, or local copyright law. You are
responsible for how you use it. If you are a rights holder and want content
removed, open an issue in this repository.

**Use at your own risk.** The build is provided as-is, without warranty of any
kind. The authors are not liable for data loss, device issues, account actions,
or legal consequences.
