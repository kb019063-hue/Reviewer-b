#!/usr/bin/env python3
"""
GitHub Actions CI Builder for AnneControl (Huawei P20 Lite ANE-LX1 Native APK).
Uses official Android SDK build-tools (aapt2, javac, d8, zipalign, apksigner).

Signing
-------
Android refuses to update an installed app whose signing certificate changed, so
the release key must survive between builds. This script therefore:

  1. restores the keystore from RELEASE_KEYSTORE_B64 (a repo secret, base64) if set;
  2. otherwise reuses ./keystore/annecontrol-release.jks if it already exists;
  3. only then falls back to generating a throwaway key, and says so loudly.

Passwords come from RELEASE_STORE_PASSWORD / RELEASE_KEY_PASSWORD and are handed to
apksigner via `env:` so they never appear on the command line or in logs.
"""
import base64
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent
SRC_MAIN = PROJECT_DIR / "src" / "main"
WORK_DIR = Path("/tmp/annecontrol-ci-work")
DIST_DIR = REPO_ROOT / "dist"
FINAL_APK = DIST_DIR / "AnneControl-P20Lite.apk"
KEYSTORE_DIR = REPO_ROOT / "keystore"
KEYSTORE_FILE = KEYSTORE_DIR / "annecontrol-release.jks"

KEY_ALIAS = "annecontrol"
# Only used for keys this script generates itself (never for a published build).
THROWAWAY_PASS = "annecontrol2026"


def run(cmd: list, show_stderr: bool = False):
    print(">>", " ".join(str(x) for x in cmd))
    proc = subprocess.run([str(x) for x in cmd], capture_output=True, text=True)
    if proc.returncode != 0:
        print("STDOUT:\n", proc.stdout)
        print("STDERR:\n", proc.stderr, file=sys.stderr)
        sys.exit(proc.returncode)
    if show_stderr and proc.stderr.strip():
        print(proc.stderr)
    return proc.stdout


def _version_key(path: Path):
    """"34.0.0" -> [34, 0, 0]; lexicographic sort would rank "9.0.0" above "34.0.0"."""
    numbers = re.findall(r"\d+", path.name)
    return [int(n) for n in numbers] or [0]


def find_sdk_tools():
    sdk_root = Path(
        os.environ.get("ANDROID_HOME")
        or os.environ.get("ANDROID_SDK_ROOT")
        or "/usr/local/lib/android/sdk"
    )
    if not sdk_root.is_dir():
        sys.exit(f"ERROR: Android SDK not found at {sdk_root}")

    bt_root = sdk_root / "build-tools"
    if not bt_root.is_dir():
        sys.exit(f"ERROR: {bt_root} is missing. Install build-tools via sdkmanager.")
    build_tools_dirs = sorted((d for d in bt_root.iterdir() if d.is_dir()), key=_version_key)
    if not build_tools_dirs:
        sys.exit("ERROR: No build-tools found in Android SDK")
    bt = build_tools_dirs[-1]

    platform_28 = sdk_root / "platforms" / "android-28" / "android.jar"
    if platform_28.exists():
        android_jar = platform_28
    else:
        platforms = sorted(
            (p for p in (sdk_root / "platforms").glob("android-*/android.jar")),
            key=_version_key,
        )
        if not platforms:
            sys.exit("ERROR: No platforms/android-*/android.jar found")
        android_jar = platforms[-1]

    print(f"Using build-tools: {bt}")
    print(f"Using android.jar: {android_jar}")
    return bt, android_jar


def resolve_keystore():
    """Returns (path, is_persistent). See the module docstring."""
    KEYSTORE_DIR.mkdir(parents=True, exist_ok=True)

    encoded = os.environ.get("RELEASE_KEYSTORE_B64", "").strip()
    if encoded:
        KEYSTORE_FILE.write_bytes(base64.b64decode(encoded))
        print(f"Restored release keystore from RELEASE_KEYSTORE_B64 -> {KEYSTORE_FILE}")
        return KEYSTORE_FILE, True

    if KEYSTORE_FILE.exists():
        print(f"Reusing existing release keystore at {KEYSTORE_FILE}")
        return KEYSTORE_FILE, True

    print("::warning::No release keystore provided - generating a THROWAWAY key. "
          "APKs built with it cannot be installed over ones signed with a different key. "
          "Set the RELEASE_KEYSTORE_B64 repository secret to fix this (see README.md).")
    run([
        "keytool", "-genkeypair",
        "-keystore", KEYSTORE_FILE,
        "-storepass", THROWAWAY_PASS,
        "-keypass", THROWAWAY_PASS,
        "-alias", KEY_ALIAS,
        "-keyalg", "RSA",
        "-keysize", "2048",
        "-validity", "10000",
        "-dname", "CN=AnneControl, OU=HuaweiP20Lite, O=AnneControl, C=GH",
    ])
    return KEYSTORE_FILE, False


def signing_password_args():
    """apksigner password flags, passed via env so they stay out of logs."""
    if os.environ.get("RELEASE_STORE_PASSWORD"):
        store = ["--ks-pass", "env:RELEASE_STORE_PASSWORD"]
    else:
        store = ["--ks-pass", f"pass:{THROWAWAY_PASS}"]
    if os.environ.get("RELEASE_KEY_PASSWORD"):
        key = ["--key-pass", "env:RELEASE_KEY_PASSWORD"]
    else:
        key = ["--key-pass", f"pass:{THROWAWAY_PASS}"]
    return store + key


def main():
    bt, android_jar = find_sdk_tools()
    aapt2 = bt / "aapt2"
    d8 = bt / "d8"
    zipalign = bt / "zipalign"
    apksigner = bt / "apksigner"

    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    WORK_DIR.mkdir(parents=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Compile Android resources
    res_zip = WORK_DIR / "compiled_res.zip"
    run([aapt2, "compile", "--dir", SRC_MAIN / "res", "-o", res_zip])

    # 2. Link base APK & generate R.java
    gen_dir = WORK_DIR / "gen"
    gen_dir.mkdir()
    unaligned_apk = WORK_DIR / "unaligned.apk"
    run([
        aapt2, "link",
        "-o", unaligned_apk,
        "-I", android_jar,
        "--manifest", SRC_MAIN / "AndroidManifest.xml",
        "-A", SRC_MAIN / "assets",
        "--java", gen_dir,
        "--min-sdk-version", "26",
        "--target-sdk-version", "28",
        res_zip,
    ])

    # 3. Compile Java sources to bytecode (.class -> classes.jar)
    classes_dir = WORK_DIR / "classes"
    classes_dir.mkdir()
    java_files = sorted(
        list((SRC_MAIN / "java").rglob("*.java")) + list(gen_dir.rglob("*.java"))
    )
    run([
        "javac",
        "-source", "8",
        "-target", "8",
        "-encoding", "UTF-8",
        "-Xlint:all,-options",
        "-bootclasspath", android_jar,
        "-d", classes_dir,
        *[str(f) for f in java_files],
    ], show_stderr=True)

    classes_jar = WORK_DIR / "classes.jar"
    run(["jar", "cf", classes_jar, "-C", classes_dir, "."])

    # 4. DEX compilation via D8
    dex_dir = WORK_DIR / "dex"
    dex_dir.mkdir()
    run([
        d8,
        "--min-api", "26",
        "--lib", android_jar,
        "--output", dex_dir,
        classes_jar,
    ])

    # 5. Add classes.dex to APK
    with zipfile.ZipFile(unaligned_apk, "a") as zf:
        zf.write(dex_dir / "classes.dex", "classes.dex", compress_type=zipfile.ZIP_DEFLATED)

    # 6. Align APK with official zipalign
    aligned_apk = WORK_DIR / "aligned.apk"
    run([zipalign, "-f", "-p", "4", unaligned_apk, aligned_apk])

    # 7. Sign (v1 + v2 + v3 for Huawei Android 9 compatibility)
    keystore, persistent = resolve_keystore()
    run([
        apksigner, "sign",
        "--ks", keystore,
        "--ks-key-alias", KEY_ALIAS,
        *signing_password_args(),
        "--v1-signing-enabled", "true",
        "--v2-signing-enabled", "true",
        "--v3-signing-enabled", "true",
        "--out", FINAL_APK,
        aligned_apk,
    ])

    # Remove .idsig if generated
    idsig = Path(str(FINAL_APK) + ".idsig")
    if idsig.exists():
        idsig.unlink()

    # 8. Verify APK signature & print badging summary
    verify_out = run([apksigner, "verify", "--verbose", "--print-certs", FINAL_APK])
    print(verify_out)
    badging_out = run([aapt2, "dump", "badging", FINAL_APK])
    print(badging_out)
    print(f"Built signed APK: {FINAL_APK} ({FINAL_APK.stat().st_size} bytes)")
    print(f"Signing key persistent: {persistent}")
    if not persistent:
        print("::warning::This build was signed with a throwaway key - existing installs "
              "will refuse to update to it.")


if __name__ == "__main__":
    main()
