# AnneControl — Huawei P20 Lite (ANE-LX1 / EMUI 9.1)

An offline Android utility that de-bloats and tunes a Huawei P20 Lite without root or a
PC: a curated bloatware catalog, a RAM sweep, a per-app cache scanner, and a hands-free
"auto-cleaner" that drives the Settings UI through an Accessibility service.

No `INTERNET` permission — nothing leaves the device.

---

## Signing

Android refuses to update an installed app whose signing certificate changed, and
GitHub Actions runners are wiped after every job — so a key generated inside the
workflow is thrown away, every build would get a new one, and installs could never
update.

So the key is committed: `anne-control-apk/signing/annecontrol.keystore`
(alias `annecontrol`, password in `ci_build.py`, valid until 2054). CI and local
builds sign with the same certificate, so a new APK installs as an upgrade, with no
secrets and no setup. This is the same mechanism as a committed `debug.keystore` in
a Gradle project.

**The catch, recorded here so it is a decision and not an accident:** that key is
public. Anyone who can read this repository can produce an APK your phone accepts as
an update to AnneControl. For a sideloaded cleanup tool with no `INTERNET` permission
that is a trade worth making, and it is why the app stays offline. Do **not** copy
this pattern to anything that handles passwords, messages or money — a keyboard or a
messenger is where a public key becomes a real keylogger path.

### Using a private key instead

Either of these overrides the committed key, in this order:

1. **Repository secret** `ANNE_SIGNING_KEY`, one line: `<base64 keystore>|<password>`
   (or `<base64>|<storepass>|<keypass>`). The older three-secret form
   `RELEASE_KEYSTORE_B64` + `RELEASE_STORE_PASSWORD` + `RELEASE_KEY_PASSWORD` still
   works and takes the same precedence. Passwords reach `apksigner` through `env:`,
   so they never appear in the log.
2. **A private keystore on the build machine**, `keystore/annecontrol-release.jks`,
   used only when `RELEASE_STORE_PASSWORD` is set. `keystore/`, `*.jks` and `*.b64`
   stay git-ignored.

Changing keys changes the signature: the first APK signed by a new key has to be
installed after an uninstall. Decide once, before the first install.

> GitHub will not let a workflow upload a secret on its own — a job declaring
> `permissions: write-all` still gets `403 Resource not accessible by integration`
> from the secrets API (verified on this repository). That is deliberate: otherwise
> any workflow, or any action it calls, could swap the signing identity. Which is
> the other reason the committed key exists — it needs nobody's involvement.


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
