#!/usr/bin/env python3
"""
GitHub Actions CI Builder for AnneControl (Huawei P20 Lite ANE-LX1 Native APK).
Uses official Android SDK build-tools (aapt2, javac, d8, zipalign, apksigner).

Signing
-------
Android refuses to update an installed app whose signing certificate changed, so
the release key must survive between builds. This script therefore:

  1. restores the keystore from ANNE_SIGNING_KEY / RELEASE_KEYSTORE_B64 if set;
  2. otherwise reuses a private ./keystore/annecontrol-release.jks if it exists;
  3. otherwise uses the committed signing/annecontrol.keystore (the default here,
     so that CI and local builds share one signature);
  4. only then falls back to generating a throwaway key, and says so loudly.

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
TEST_SRC = PROJECT_DIR / "test" / "java"
# Classes with no Android imports, so they can be compiled and run on a plain JVM.
PURE_JAVA = ("HuaweiCatalog.java", "QueuePlanner.java")
KEYSTORE_DIR = REPO_ROOT / "keystore"
# Signing identity shared through the repository, the same way a committed
# debug.keystore works in a Gradle project: every build (CI included) signs with
# this one key, so APKs install as upgrades. Its password is public too - that is
# what "committed key" means. See README "Signing" for the trade-off and for the
# private-key alternative (ANNE_SIGNING_KEY), which takes precedence when set.
SIGNING_DIR = PROJECT_DIR / "signing"
COMMITTED_KEYSTORE = SIGNING_DIR / "annecontrol.keystore"
COMMITTED_STORE_PASSWORD = "23Spq3Q8UDnLcoXUpRG5m3GA"
COMMITTED_KEY_PASSWORD = "23Spq3Q8UDnLcoXUpRG5m3GA"
# Certificate digest of the committed key. Guarded at the end of every build: if an
# APK ever comes out signed by anything else, installed copies could no longer be
# updated, and that must fail the build instead of shipping quietly.
EXPECTED_SIGNER_SHA256 = "c264cf3d7e1f8eabd20ae0b9f3a732f3a34315b4a352367285872e88d16f3c29"
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


def run_unit_tests():
    """
    Compiles the Android-free logic (QueuePlanner + HuaweiCatalog) together with the
    tests and runs them on the desktop JVM. A failing assertion fails the APK build.
    """
    sources = []
    for name in PURE_JAVA:
        found = list((SRC_MAIN / "java").rglob(name))
        if not found:
            sys.exit(f"ERROR: {name} not found for the unit-test step")
        sources.extend(found)
    test_sources = sorted(TEST_SRC.rglob("*.java"))
    if not test_sources:
        sys.exit(f"ERROR: no test sources found under {TEST_SRC}")
    sources.extend(test_sources)

    out_dir = Path("/tmp/annecontrol-unit-tests")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    print("Running JVM unit tests...")
    run(["javac", "-encoding", "UTF-8", "-Xlint:all,-options", "-d", out_dir]
        + [str(f) for f in sources], show_stderr=True)
    output = run(["java", "-cp", out_dir, "com.annecontrol.p20lite.QueuePlannerTest"])
    print(output)


def resolve_keystore():
    """
    Returns (path, is_persistent, passwords).

    `passwords` is None when apksigner should take them from the environment
    (secret/local-key cases) or use the throwaway default, and a (store, key)
    tuple for the committed key, whose password is public anyway.
    """
    KEYSTORE_DIR.mkdir(parents=True, exist_ok=True)

    # Single-secret form, for people who would rather paste once than three times:
    #   "<base64 keystore>|<password>"  or  "<base64 keystore>|<storepass>|<keypass>"
    combined = os.environ.get("ANNE_SIGNING_KEY", "").strip()
    if combined:
        parts = combined.split("|")
        if len(parts) not in (2, 3):
            sys.exit("ERROR: ANNE_SIGNING_KEY must be '<base64 keystore>|<password>' "
                     "or '<base64 keystore>|<storepass>|<keypass>'")
        try:
            blob = base64.b64decode(parts[0], validate=True)
        except Exception as exc:
            sys.exit(f"ERROR: ANNE_SIGNING_KEY does not start with valid base64: {exc}")
        # A truncated or re-encoded paste otherwise fails much later with a
        # confusing "keystore password was incorrect" from apksigner.
        if len(blob) < 512 or not (blob[:2] == b"\x30\x82" or blob[:4] == b"\xfe\xed\xfe\xed"):
            sys.exit("ERROR: ANNE_SIGNING_KEY does not look like a JKS/PKCS12 keystore "
                     f"({len(blob)} bytes decoded). Re-copy the whole line.")
        KEYSTORE_FILE.write_bytes(blob)
        os.chmod(KEYSTORE_FILE, 0o600)
        if not os.environ.get("RELEASE_STORE_PASSWORD"):
            os.environ["RELEASE_STORE_PASSWORD"] = parts[1]
        if not os.environ.get("RELEASE_KEY_PASSWORD"):
            os.environ["RELEASE_KEY_PASSWORD"] = parts[-1]
        # (env vars only: apksigner is invoked with env: references, never literals)
        print(f"Restored release keystore from ANNE_SIGNING_KEY -> {KEYSTORE_FILE}")
        return KEYSTORE_FILE, True, None

    encoded = os.environ.get("RELEASE_KEYSTORE_B64", "").strip()
    if encoded:
        KEYSTORE_FILE.write_bytes(base64.b64decode(encoded))
        print(f"Restored release keystore from RELEASE_KEYSTORE_B64 -> {KEYSTORE_FILE}")
        return KEYSTORE_FILE, True, None

    if KEYSTORE_FILE.exists():
        # Only honour a private local key when we also know its password; otherwise
        # signing would fail later with a confusing "password was incorrect".
        if os.environ.get("RELEASE_STORE_PASSWORD"):
            print(f"Reusing existing release keystore at {KEYSTORE_FILE}")
            return KEYSTORE_FILE, True, None
        print(f"::warning::Ignoring {KEYSTORE_FILE}: RELEASE_STORE_PASSWORD is not set. "
              "Falling back to the committed signing key.")

    if COMMITTED_KEYSTORE.exists():
        print(f"Using the committed signing key at {COMMITTED_KEYSTORE}")
        return COMMITTED_KEYSTORE, True, (COMMITTED_STORE_PASSWORD, COMMITTED_KEY_PASSWORD)

    print("::warning::No release keystore provided - generating a THROWAWAY key. "
          "APKs built with it cannot be installed over ones signed with a different key. "
          "Commit a signing key at anne-control-apk/signing/annecontrol.keystore "
          "or add the ANNE_SIGNING_KEY repository secret (see README.md).")
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
    return KEYSTORE_FILE, False, None


def signing_password_args(passwords=None):
    """apksigner password flags; secrets go via env: so they stay out of logs."""
    if passwords is not None:
        store, key = passwords
        # The committed key's password is published in this file, so passing it on
        # the command line exposes nothing that is not already public.
        return ["--ks-pass", f"pass:{store}", "--key-pass", f"pass:{key}"]
    if os.environ.get("RELEASE_STORE_PASSWORD"):
        store = ["--ks-pass", "env:RELEASE_STORE_PASSWORD"]
    else:
        store = ["--ks-pass", f"pass:{THROWAWAY_PASS}"]
    if os.environ.get("RELEASE_KEY_PASSWORD"):
        key = ["--key-pass", "env:RELEASE_KEY_PASSWORD"]
    else:
        key = ["--key-pass", f"pass:{THROWAWAY_PASS}"]
    return store + key


def assert_signer(verify_output, expected_hex):
    """The APK must carry the committed certificate, or upgrades break silently."""
    match = re.search(r"Signer #1 certificate SHA-256 digest:\s*([0-9a-fA-F]+)", verify_output)
    if not match:
        sys.exit("ERROR: could not read the signer certificate from apksigner output")
    actual = match.group(1).lower()
    if actual != expected_hex:
        sys.exit(
            "ERROR: APK is signed by\n  " + actual + "\nbut the committed key is\n  "
            + expected_hex + "\nA different certificate means installed copies cannot be "
            "updated (Android refuses the upgrade). If the key was rotated on purpose, "
            "update EXPECTED_SIGNER_SHA256 and expect one uninstall."
        )
    print(f"Signer matches the committed key: {actual[:16]}...")


def main():
    # Fast-fail on logic regressions before touching the Android toolchain.
    run_unit_tests()

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
    keystore, persistent, passwords = resolve_keystore()
    run([
        apksigner, "sign",
        "--ks", keystore,
        "--ks-key-alias", KEY_ALIAS,
        *signing_password_args(passwords),
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
    if persistent and keystore == COMMITTED_KEYSTORE:
        assert_signer(verify_out, EXPECTED_SIGNER_SHA256)
    badging_out = run([aapt2, "dump", "badging", FINAL_APK])
    print(badging_out)
    print(f"Built signed APK: {FINAL_APK} ({FINAL_APK.stat().st_size} bytes)")
    print(f"Signing key persistent: {persistent}")
    if not persistent:
        print("::warning::This build was signed with a throwaway key - existing installs "
              "will refuse to update to it.")


if __name__ == "__main__":
    main()
