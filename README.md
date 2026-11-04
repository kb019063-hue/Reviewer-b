# AnneControl — Huawei P20 Lite (ANE-LX1 / EMUI 9.1)

An offline Android utility that de-bloats and tunes a Huawei P20 Lite without root or a
PC: a curated bloatware catalog, a RAM sweep, a per-app cache scanner, and a hands-free
"auto-cleaner" that drives the Settings UI through an Accessibility service.

No `INTERNET` permission — nothing leaves the device.

---

## Signing key (do this once)

Android refuses to update an installed app whose signing certificate changed. Because
GitHub Actions runners are ephemeral, a keystore generated inside the workflow is thrown
away after every job — so **every build would get a new key and existing installs could
never update**. The key therefore lives in a repository secret.

```bash
# 1. Create the release key ONCE, somewhere safe (it is not recoverable)
mkdir -p keystore
keytool -genkeypair \
  -keystore keystore/annecontrol-release.jks \
  -storepass '<your-store-password>' \
  -keypass '<your-key-password>' \
  -alias annecontrol -keyalg RSA -keysize 2048 -validity 10000 \
  -dname "CN=AnneControl, OU=HuaweiP20Lite, O=AnneControl, C=GH"

# 2. Base64 it and add it to the repo's Actions secrets
base64 -w0 keystore/annecontrol-release.jks
```

Then in **Settings → Secrets and variables → Actions**, add:

| Secret | Value |
|---|---|
| `RELEASE_KEYSTORE_B64` | output of the `base64 -w0` command above |
| `RELEASE_STORE_PASSWORD` | the `-storepass` you chose |
| `RELEASE_KEY_PASSWORD` | the `-keypass` you chose |

`keystore/`, `*.jks` and `*.b64` are git-ignored — never commit the key.

If the secret is missing, `ci_build.py` still produces a working APK, but it prints a
GitHub Actions warning: that build is signed with a **throwaway** key and will not install
over a previously released one.

---

## Building

The build uses the plain Android SDK tools directly (`aapt2`, `javac`, `d8`, `zipalign`,
`apksigner`) — no Gradle.

```bash
# requires ANDROID_HOME pointing at an SDK with build-tools + platforms/android-28
python3 anne-control-apk/ci_build.py
# -> dist/AnneControl-P20Lite.apk
```

CI (`.github/workflows/build-annecontrol-apk.yml`) uploads the APK as an artifact on every
push, and publishes it to the `latest-apk` GitHub Release **only from `main`**.

---

## Tests

Two suites run in CI (`.github/workflows/build-annecontrol-apk.yml`):

```bash
# Pure-logic tests for the automation queue, on a plain JVM (no device, no SDK).
# ci_build.py runs these first and aborts the APK build if they fail.
javac -d /tmp/t anne-control-apk/src/main/java/com/annecontrol/p20lite/{HuaweiCatalog,QueuePlanner}.java \
      anne-control-apk/test/java/com/annecontrol/p20lite/QueuePlannerTest.java
java -cp /tmp/t com.annecontrol.p20lite.QueuePlannerTest

# WebView UI tests: the real index.html under jsdom with a stub AnneNative bridge.
cd test/ui && npm install && node ui_test.js
```

## How the cleanup behaves

* **Sweep scope** — "Bloat + all apps" (default) or "Curated bloat only". Change it on the
  Boost tab.
* **Keep Alive list** — persisted exemptions, **empty by default**. Nothing is hard-coded
  as unkillable: chat apps that keep a socket open and keep receiving messages after being
  swiped out of Recents are exactly what the sweep is meant to stop, so whether WhatsApp
  keeps running is the user's choice, not the app's.
* **Sweep numbers are measured, not invented** — the banner reports how many stop requests
  were sent and the real measured RAM delta, which may be 0 or negative.
* **Cancelling a run** — the auto-cleaner drives the Settings UI, so the app itself is not
  on screen while it runs. Two escape hatches: the **STOP** action on the ongoing
  notification, or pressing **Volume Down** (works even if notifications are suppressed).
  The in-app back button also cancels once you are back in the app.
* **Safety gate** — before clicking Force stop / Disable / Clear cache, the accessibility
  service verifies the visible Settings page really belongs to the queued app (by label or
  package id). If it cannot verify the screen, the run aborts instead of clicking blind.

See [`docs/CODE_REVIEW.md`](docs/CODE_REVIEW.md) for the full review, including the
findings these fixes address and what is still open.
