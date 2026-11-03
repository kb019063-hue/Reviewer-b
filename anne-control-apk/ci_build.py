#!/usr/bin/env python3
"""
GitHub Actions CI Builder for AnneControl (Huawei P20 Lite ANE-LX1 Native APK).
Uses official Android SDK build-tools (aapt2, javac, d8, zipalign, apksigner).
"""
import os
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


def run(cmd: list[str]):
    print(">>", " ".join(str(x) for x in cmd))
    proc = subprocess.run([str(x) for x in cmd], capture_output=True, text=True)
    if proc.returncode != 0:
        print("STDOUT:\n", proc.stdout)
        print("STDERR:\n", proc.stderr, file=sys.stderr)
        sys.exit(proc.returncode)
    return proc.stdout


def find_sdk_tools():
    sdk_root = Path(
        os.environ.get("ANDROID_HOME")
        or os.environ.get("ANDROID_SDK_ROOT")
        or "/usr/local/lib/android/sdk"
    )
    if not sdk_root.exists():
        sys.exit(f"ERROR: Android SDK not found at {sdk_root}")

    build_tools_dirs = sorted((sdk_root / "build-tools").iterdir())
    if not build_tools_dirs:
        sys.exit("ERROR: No build-tools found in Android SDK")
    bt = build_tools_dirs[-1]

    platform_28 = sdk_root / "platforms" / "android-28" / "android.jar"
    if platform_28.exists():
        android_jar = platform_28
    else:
        platforms = sorted((sdk_root / "platforms").glob("android-*/android.jar"))
        if not platforms:
            sys.exit("ERROR: No platforms/android-*/android.jar found")
        android_jar = platforms[-1]

    print(f"Using build-tools: {bt}")
    print(f"Using android.jar: {android_jar}")
    return bt, android_jar


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
        "--min-sdk-version", "24",
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
        "-Xlint:none",
        "-bootclasspath", android_jar,
        "-d", classes_dir,
        *[str(f) for f in java_files],
    ])

    classes_jar = WORK_DIR / "classes.jar"
    run(["jar", "cf", classes_jar, "-C", classes_dir, "."])

    # 4. DEX compilation via D8
    dex_dir = WORK_DIR / "dex"
    dex_dir.mkdir()
    run([
        d8,
        "--min-api", "24",
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

    # 7. Generate signing keystore & sign APK (v1 + v2 + v3 for Huawei Android 9 compatibility)
    keystore = WORK_DIR / "annecontrol-release.jks"
    run([
        "keytool", "-genkeypair",
        "-keystore", keystore,
        "-storepass", "annecontrol2026",
        "-keypass", "annecontrol2026",
        "-alias", "annecontrol",
        "-keyalg", "RSA",
        "-keysize", "2048",
        "-validity", "10000",
        "-dname", "CN=AnneControl, OU=HuaweiP20Lite, O=AnneControl, C=GH",
    ])

    run([
        apksigner, "sign",
        "--ks", keystore,
        "--ks-key-alias", "annecontrol",
        "--ks-pass", "pass:annecontrol2026",
        "--key-pass", "pass:annecontrol2026",
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
    verify_out = run([apksigner, "verify", "--verbose", FINAL_APK])
    print(verify_out)
    badging_out = run([aapt2, "dump", "badging", FINAL_APK])
    print(badging_out)
    print(f"Built signed APK: {FINAL_APK} ({FINAL_APK.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
