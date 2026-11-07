#!/usr/bin/env python3
"""
GitHub Actions CI Builder for AnneControl (Huawei P20 Lite ANE-LX1 Native APK).
Uses official Android SDK build-tools (aapt2, javac, d8, zipalign, apksigner).

Signing
-------
Release builds require a persistent private key supplied through ANNE_SIGNING_KEY,
RELEASE_KEYSTORE_B64, or a local ignored keystore. The explicit --debug-test mode uses the
separate ANNE_TEST_SIGNING_KEY when configured, falling back to a one-run local/CI key only
when absent. Test APKs are never releases. CI release builds also require ANNE_SIGNER_SHA256
to pin the expected signing certificate. Passwords are passed through environment references.
"""
import argparse
import base64
import os
import re
import secrets
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
DEBUG_APK = DIST_DIR / "AnneControl-P20Lite-Debug.apk"
DEBUG_KEY_ALIAS = "annecontrol-debug-test"
TEST_SRC = PROJECT_DIR / "test" / "java"
# Classes with no Android imports, so they can be compiled and run on a plain JVM.
PURE_JAVA = ("HuaweiCatalog.java", "QueuePlanner.java")
KEYSTORE_DIR = REPO_ROOT / "keystore"
KEYSTORE_FILE = KEYSTORE_DIR / "annecontrol-release.jks"
KEY_ALIAS = "annecontrol"


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
    """Restore or locate a private keystore; never create or use a public key."""
    KEYSTORE_DIR.mkdir(parents=True, exist_ok=True)

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
        if len(blob) < 512 or not (blob[:2] == b"\x30\x82" or blob[:4] == b"\xfe\xed\xfe\xed"):
            sys.exit("ERROR: ANNE_SIGNING_KEY does not look like a JKS/PKCS12 keystore "
                     f"({len(blob)} bytes decoded). Re-copy the whole line.")
        KEYSTORE_FILE.write_bytes(blob)
        os.chmod(KEYSTORE_FILE, 0o600)
        if not os.environ.get("RELEASE_STORE_PASSWORD"):
            os.environ["RELEASE_STORE_PASSWORD"] = parts[1]
        if not os.environ.get("RELEASE_KEY_PASSWORD"):
            os.environ["RELEASE_KEY_PASSWORD"] = parts[-1]
        print("Restored private release keystore from ANNE_SIGNING_KEY")
        return KEYSTORE_FILE

    encoded = os.environ.get("RELEASE_KEYSTORE_B64", "").strip()
    if encoded:
        try:
            KEYSTORE_FILE.write_bytes(base64.b64decode(encoded, validate=True))
        except Exception as exc:
            sys.exit(f"ERROR: RELEASE_KEYSTORE_B64 is invalid: {exc}")
        os.chmod(KEYSTORE_FILE, 0o600)
        print("Restored private release keystore from RELEASE_KEYSTORE_B64")
        return KEYSTORE_FILE

    if KEYSTORE_FILE.exists() and os.environ.get("RELEASE_STORE_PASSWORD"):
        print(f"Using ignored local private keystore: {KEYSTORE_FILE}")
        return KEYSTORE_FILE

    sys.exit("ERROR: no private signing key supplied. Configure ANNE_SIGNING_KEY or "
             "RELEASE_KEYSTORE_B64 + passwords, or provide ignored keystore/annecontrol-release.jks "
             "and RELEASE_STORE_PASSWORD. Never commit the keystore.")


def signing_password_args():
    """apksigner password flags; passwords are passed via env: and stay out of logs."""
    if not os.environ.get("RELEASE_STORE_PASSWORD"):
        sys.exit("ERROR: RELEASE_STORE_PASSWORD is required")
    if not os.environ.get("RELEASE_KEY_PASSWORD"):
        os.environ["RELEASE_KEY_PASSWORD"] = os.environ["RELEASE_STORE_PASSWORD"]
    return ["--ks-pass", "env:RELEASE_STORE_PASSWORD", "--key-pass", "env:RELEASE_KEY_PASSWORD"]


def create_ephemeral_test_keystore(path: Path):
    """Create a local fallback key when no persistent test signer is configured."""
    keytool = shutil.which("keytool")
    if not keytool:
        sys.exit("ERROR: keytool is required for a test-only signed APK")
    password = secrets.token_urlsafe(32)
    os.environ["ANNE_TEST_KEY_PASSWORD"] = password
    run([
        keytool, "-genkeypair", "-noprompt",
        "-keystore", path,
        "-storetype", "PKCS12",
        "-storepass:env", "ANNE_TEST_KEY_PASSWORD",
        "-keypass:env", "ANNE_TEST_KEY_PASSWORD",
        "-alias", DEBUG_KEY_ALIAS,
        "-keyalg", "RSA",
        "-keysize", "2048",
        "-validity", "3650",
        "-dname", "CN=AnneControl Temporary Test Build",
    ])
    return path


def resolve_test_keystore(path: Path):
    """Use a persistent Actions test signer when configured; otherwise use a disposable key."""
    combined = os.environ.get("ANNE_TEST_SIGNING_KEY", "").strip()
    if not combined:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print("::warning::ANNE_TEST_SIGNING_KEY is not set; this run will use a temporary signer and cannot update a previous test install.")
        return create_ephemeral_test_keystore(path), False

    parts = combined.split("|")
    if len(parts) != 2 or not parts[1]:
        sys.exit("ERROR: ANNE_TEST_SIGNING_KEY must be '<base64 PKCS12 keystore>|<password>'")
    try:
        blob = base64.b64decode(parts[0], validate=True)
    except Exception as exc:
        sys.exit(f"ERROR: ANNE_TEST_SIGNING_KEY is not valid base64: {exc}")
    if len(blob) < 512 or blob[0] != 0x30:
        sys.exit("ERROR: ANNE_TEST_SIGNING_KEY does not look like a PKCS12 keystore")
    path.write_bytes(blob)
    os.chmod(path, 0o600)
    os.environ["ANNE_TEST_KEY_PASSWORD"] = parts[1]
    return path, True


def assert_signer(verify_output, expected_hex):
    """Pin the APK signer certificate so a wrong key cannot silently ship."""
    match = re.search(r"certificate SHA-256 digest:\s*([0-9a-fA-F:]+)", verify_output)
    if not match:
        tail = " | ".join(verify_output.strip().splitlines()[:12])
        sys.exit("ERROR: could not read the signer certificate from apksigner output: " + tail)
    actual = match.group(1).replace(":", "").lower()
    expected = expected_hex.replace(":", "").lower()
    if actual != expected:
        sys.exit("ERROR: APK signer digest does not match ANNE_SIGNER_SHA256. "
                 "Check that the configured private key and expected digest belong together.")
    print(f"Signer matches the configured private key: {actual[:16]}...")


def main():
    parser = argparse.ArgumentParser(description="Build AnneControl for Android 9 / ANE-LX1")
    parser.add_argument(
        "--debug-test", action="store_true",
        help="build a test-only APK using ANNE_TEST_SIGNING_KEY, or a one-run fallback key",
    )
    parser.add_argument("--version-code", type=int, help="optional Android versionCode override")
    args = parser.parse_args()
    if args.version_code is not None and not (1 <= args.version_code <= 2100000000):
        parser.error("--version-code must be between 1 and 2100000000")

    # Both build modes run the pure-logic tests first. Release mode keeps the
    # stable private-key guard; test mode remains separate from release signing.
    run_unit_tests()
    keystore = None
    if not args.debug_test:
        keystore = resolve_keystore()
        if os.environ.get("GITHUB_ACTIONS") == "true" and not os.environ.get("ANNE_SIGNER_SHA256", "").strip():
            sys.exit("ERROR: set the ANNE_SIGNER_SHA256 repository variable before building in CI")

    bt, android_jar = find_sdk_tools()
    aapt2 = bt / "aapt2"
    d8 = bt / "d8"
    zipalign = bt / "zipalign"
    apksigner = bt / "apksigner"

    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    WORK_DIR.mkdir(parents=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    output_apk = DEBUG_APK if args.debug_test else FINAL_APK
    persistent_test_key = False
    if args.debug_test:
        keystore, persistent_test_key = resolve_test_keystore(WORK_DIR / "annecontrol-debug-test.p12")
        signer_alias = DEBUG_KEY_ALIAS
        password_args = ["--ks-pass", "env:ANNE_TEST_KEY_PASSWORD", "--key-pass", "env:ANNE_TEST_KEY_PASSWORD"]
    else:
        signer_alias = KEY_ALIAS
        password_args = signing_password_args()

    # 1. Compile Android resources
    res_zip = WORK_DIR / "compiled_res.zip"
    run([aapt2, "compile", "--dir", SRC_MAIN / "res", "-o", res_zip])

    # 2. Link base APK & generate R.java
    gen_dir = WORK_DIR / "gen"
    gen_dir.mkdir()
    unaligned_apk = WORK_DIR / "unaligned.apk"
    link_command = [
        aapt2, "link",
        "-o", unaligned_apk,
        "-I", android_jar,
        "--manifest", SRC_MAIN / "AndroidManifest.xml",
        "-A", SRC_MAIN / "assets",
        "--java", gen_dir,
        "--min-sdk-version", "26",
        "--target-sdk-version", "28",
    ]
    if args.version_code is not None:
        link_command.extend(["--version-code", str(args.version_code)])
    link_command.append(res_zip)
    run(link_command)

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

    # 7. Sign (v1 + v2 + v3 for Huawei Android 9 compatibility).
    # Test mode is separate from release signing and is never a release artifact.
    run([
        apksigner, "sign",
        "--ks", keystore,
        "--ks-key-alias", signer_alias,
        *password_args,
        "--v1-signing-enabled", "true",
        "--v2-signing-enabled", "true",
        "--v3-signing-enabled", "true",
        "--out", output_apk,
        aligned_apk,
    ])

    # Remove .idsig if generated
    idsig = Path(str(output_apk) + ".idsig")
    if idsig.exists():
        idsig.unlink()

    # 8. Verify APK signature & print badging summary
    verify_out = run([apksigner, "verify", "--verbose", "--print-certs", output_apk])
    print(verify_out)
    if args.debug_test:
        if persistent_test_key:
            print("Test-only APK uses the persistent test signer; later builds can update it in place.")
        else:
            print("Test APK uses a temporary signer; uninstall before replacing it with a later build.")
    else:
        expected_signer = os.environ.get("ANNE_SIGNER_SHA256", "").strip()
        if expected_signer:
            assert_signer(verify_out, expected_signer)
        elif os.environ.get("GITHUB_ACTIONS") == "true":
            sys.exit("ERROR: set the ANNE_SIGNER_SHA256 repository variable to the private key's "
                     "certificate SHA-256 digest before building in CI")
        else:
            print("::warning::ANNE_SIGNER_SHA256 is not set; signer was verified by apksigner "
                  "but not pinned to an expected certificate.")
    badging_out = run([aapt2, "dump", "badging", output_apk])
    print(badging_out)
    mode = "test-only debug" if args.debug_test else "release"
    print(f"Built {mode} APK: {output_apk} ({output_apk.stat().st_size} bytes)")


def _report_failure(code):
    """Turn a SystemExit string into a ::error:: annotation so CI failures explain themselves."""
    if isinstance(code, str) and code.strip():
        message = " ".join(str(code).split())
        print(f"::error::{message[:900]}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as exc:
        _report_failure(exc.code)
        raise
