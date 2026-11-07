# AnneControl — Huawei P20 Lite (ANE-LX1 / EMUI 9.1)

An offline Android utility for Huawei P20 Lite (ANE-LX1 / EMUI 9.1) maintenance and
customization without root: a curated bloatware catalog, best-effort background-process
requests, a per-app cache scanner, Settings automation through an Accessibility service,
and user-mediated Huawei `.hwt` theme preview/import. Theme archives are inspected locally,
shown using packaged preview artwork, copied only through Android's file/folder pickers,
and must still be applied by Huawei Themes.

No `INTERNET` permission — the app does not transmit data itself. The optional support report is generated on-device and includes model/build, app version, relevant permission states, Huawei Themes availability, and the last theme-package inspection. It excludes serial/IMEI, Android ID, contacts, personal files, and installed-app lists; it is shared only if the user chooses a target in Android's share sheet.

---

## Signing

The APK must be signed with a stable **private** key: Android rejects an update if
its signer changes. The previously committed signing key was public, so it has been
removed from the working tree and must no longer be used. Removing it here does not
erase it from earlier Git history; treat that old certificate as compromised.

**Rotation consequence:** APKs signed with the replacement key cannot update installs
signed with the exposed key. Those users must uninstall the old app and install the
newly signed APK. Do this before distributing a replacement release.

CI and local builds now refuse to generate or use a throwaway/committed key. Configure
one private key using either:

1. GitHub Actions secret `ANNE_SIGNING_KEY`, a single line in the form
   `<base64-keystore>|<password>` or `<base64-keystore>|<store-password>|<key-password>`; or
2. the legacy secrets `RELEASE_KEYSTORE_B64`, `RELEASE_STORE_PASSWORD`, and
   `RELEASE_KEY_PASSWORD`; or
3. locally, `keystore/annecontrol-release.jks` with `RELEASE_STORE_PASSWORD` (and
   optionally `RELEASE_KEY_PASSWORD`). `keystore/`, `*.jks`, `*.keystore`, and `*.b64`
   are git-ignored.

Use the alias `annecontrol` (or update `KEY_ALIAS` in the build script to match your
keystore). Set the non-secret GitHub repository variable `ANNE_SIGNER_SHA256` to the
new certificate's SHA-256 digest. CI fails if the built APK's certificate does not match
it. Generate and store the new key securely; never commit it or paste its private
material into chat.


## Building

The build uses the plain Android SDK tools directly (`aapt2`, `javac`, `d8`, `zipalign`,
`apksigner`) — no Gradle.

```bash
# requires ANDROID_HOME pointing at an SDK with build-tools + platforms/android-28
python3 anne-control-apk/ci_build.py
# -> dist/AnneControl-P20Lite.apk
```

CI (`.github/workflows/build-annecontrol-apk.yml`) runs the UI/JVM tests on `arena/**`
and `main`; only `main` receives signing material, builds the APK, uploads the artifact,
and publishes the `latest-apk` release.

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
cd test/ui && npm ci && node ui_test.js
```

## How the cleanup behaves

* **Sweep scope** — "Bloat + all apps" (default) or "Curated bloat only". Change it on the
  Boost tab.
* **Keep Alive list** — persisted exemptions, **empty by default**. Nothing is hard-coded
  as unkillable: apps on this list are excluded from background-process requests. Requests
  for other apps may have no effect or the app may restart, depending on Android.
* **Sweep requests are not force-stops** — Android may ignore a background-process request
  or restart an app. The banner reports requests sent and a noisy measured RAM delta, which
  may be 0 or negative; neither proves which apps were terminated.
* **Cancelling a run** — the auto-cleaner drives the Settings UI, so the app itself is not
  on screen while it runs. Two escape hatches: the **STOP** action on the ongoing
  notification, or pressing **Volume Down** (works even if notifications are suppressed).
  The in-app back button also cancels once you are back in the app.
* **Device scope** — Settings automation is enabled only on Huawei ANE-LX1 / Android 9
  (EMUI 9.1); the bloat catalog is firmware-specific.
* **Safety gate** — before acting, the accessibility service verifies the visible Settings
  page belongs to the queued app, checks an action-specific confirmation prompt, and waits
  for the resulting control state before counting a success. If it cannot verify the screen
  or outcome, the run fails closed.

See [`docs/CODE_REVIEW.md`](docs/CODE_REVIEW.md) for the historical review and the current
follow-up status; historical findings and line numbers are explicitly marked.
