# AnneControl (P20 Lite) — Code Review

**Scope:** `anne-control-apk/` (Java + WebView UI), `ci_build.py`, `.github/workflows/`, `AndroidManifest.xml`
**Commit reviewed:** `ad9e9ef` ("Fix accessibility leaks, multilingual support, auto-publish APK release & prevent background app reloads")
**Reviewer note:** findings below are ordered by *user-facing risk*, not by file. Line numbers refer to the reviewed commit.

---

## 0. TL;DR scorecard

| # | Severity | Finding | Where |
|---|---|---|---|
| 1 | 🔴 Critical | A running automation **cannot be stopped** — the app is not in the foreground, and the service-connected check produces false positives, so the phone can walk through Settings on its own with nothing clicking | `SystemBridge:81`, `AnneAccessibilityService:46`, `AutomationEngine:154`, `index.html:761` |
| 2 | 🔴 Critical | **No verification that the on-screen App-info page is the intended package** before Force-Stop / Disable → can disable the wrong app | `AnneAccessibilityService:84-88`, `:110-113` |
| 3 | 🔴 Critical | Release keystore is regenerated **on every CI run** → every build has a different signing key → in-place updates fail; password hardcoded; `.jks` not git-ignored | `ci_build.py:58-77`, `.gitignore:5` |
| 4 | 🟠 High | Fabricated metrics: "Swept N services / freed ≥16 MB" is not measured | `SystemBridge:266-295` |
| 5 | 🟠 High | RAM sweep kills **every third-party app** (music, downloads, banking) using a 9-item denylist | `SystemBridge:278-290`, `:645-654` |
| 6 | 🟠 High | Unescaped app labels injected via `innerHTML` while a JS bridge is attached → script injection can trigger native automation | `index.html:746-752`, `:807-815` |
| 7 | 🟠 High | Cache scan blocks the JS thread for seconds with no loading state; scans *all* installed apps | `SystemBridge:364-402`, `index.html:781` |
| 8 | 🟠 High | Timeout-driven state machine silently skips work and inflates "success" counts | `AutomationQueue` (`AutomationEngine:43`, `:97`) |
| 9 | 🟠 High | Confirm-dialog label list overlaps action labels → re-clicks the action button | `AnneAccessibilityService:41-44`, `:275-300` |
| 10 | 🟡 Medium | `start()` while running can wedge the engine / skip a package (no generation token) | `AutomationEngine:52`, `:146` |
| 11 | 🟡 Medium | Accessibility tree searched once **per label per event** (up to 9 full traversals) → Settings jank | `AnneAccessibilityService:246-273` |
| 12 | 🟡 Medium | CI has no `concurrency` group, publishes a GitHub Release from every `arena/**` push, lexicographic tool selection, creds in source | `build-annecontrol-apk.yml`, `ci_build.py:39-50` |
| 13 | 🟡 Medium | Dead/unusable permissions declared, misleading "grant via ADB" instruction | `AndroidManifest.xml:11-19`, `index.html:526` |

**What is genuinely good:** zero `INTERNET` permission (the "100% offline" claim is true), `Task`-safe static singleton with app context, defensive `try/catch` almost everywhere, node recycling discipline in the accessibility code, and a build that verifies its own signature with `apksigner verify`.

---

## 1. Critical

### 1.1 You cannot stop an automation once it starts (and it can start with no service attached)

`AutomationEngine.start()` is invoked from the WebView bridge while `MainActivity` is in the foreground. The engine immediately fires `startActivity(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)`, which puts **Settings on top of the app**. From that moment:

* the user cannot reach the app's UI (the only cancel path is `MainActivity.onBackPressed` → `AutomationEngine.stop()`, `MainActivity:57-67`);
* there is no notification, overlay, or hardware-key escape hatch;
* the engine keeps chaining through the whole queue.

Worse, the pre-flight check is not trustworthy:

```java
// SystemBridge.java:81-94
public boolean hasAccessibilityEnabled() {
    if (AnneAccessibilityService.isServiceConnected()) return true;
    String enabled = Settings.Secure.getString(cr, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES);
    return enabled != null && enabled.contains(ctx.getPackageName());   // ← false positive
}
```

`ENABLED_ACCESSIBILITY_SERVICES` is a **persisted preference**. On EMUI 9.1 the service is routinely killed/disabled by the very battery manager this app is fighting (`com.huawei.systemmanager`). The setting still lists the package, `isServiceConnected()` is `false`, and `startAutomation()` happily returns `{"ok":true}`. The result: the phone opens App-info screens one after another for ~4.2 s each (`AutomationEngine:167`) with nothing clicking, and the user must fight the back stack to stop it.

`AnneAccessibilityService` also never clears the flag in `onDestroy()` (`:56-60` only handles `onUnbind`), so a service killed by the OS can leave `serviceConnected == true` forever.

**Fix (all three are needed):**

```java
// SystemBridge.java — gate on the live connection, not the preference
public boolean hasAccessibilityEnabled() {
    return AnneAccessibilityService.isServiceConnected();
}
```

```java
// AnneAccessibilityService.java — reject stale state
@Override public boolean onUnbind(Intent i) { serviceConnected = false; return super.onUnbind(i); }
@Override public void onDestroy() { serviceConnected = false; super.onDestroy(); }
```

Plus an escape hatch. The cheapest reliable one on API 26+ is a foreground/ongoing notification with a **Stop** action (`NotificationManager` is already implicitly available; no extra permission at target 28):

```java
// AutomationEngine.start()
Notification.Builder b = new Notification.Builder(appContext, CHANNEL_RUNNING)
    .setSmallIcon(android.R.drawable.stat_notify_sync)
    .setContentTitle("AnneControl is running")
    .setContentText(statusMessage)
    .setOngoing(true)
    .addAction(new Notification.Action.Builder(null, "Stop", stopPendingIntent()).build());
notificationManager.notify(NOTIF_ID, b.build());
```

An `AccessibilityService` can also register a hardware stop: add `android:canRequestFilterKeyEvents="true"` to the service config and override `onKeyEvent()` to abort on `VOLUME_DOWN`. And `startAutomation()` should return `{"ok":false,"needsAccessibility":true}` when `!isServiceConnected()`, with `index.html` surfacing that (see 3.1).

### 1.2 Force Stop / Disable is clicked without verifying the target app

```java
// AnneAccessibilityService.java:84-88
CharSequence rootPkg = root.getPackageName();
if (rootPkg == null || !rootPkg.toString().contains("settings")) return;
```

This is the **only** identity check. Any Settings screen that happens to be showing qualifies, and then the first node labelled "Force stop" / "Disable" anywhere in the tree is clicked (`:105-136`, `:138-177`). Three concrete ways this bites a real user:

1. **Stale activity reuse.** `AutomationEngine:162-165` uses `FLAG_ACTIVITY_CLEAR_TOP` on `ACTION_APPLICATION_DETAILS_SETTINGS`. `CLEAR_TOP` matches by *component*, so an already-running App-info activity can be brought to the front and handed a new intent — and Android Settings' app-details screen reads its package in `onCreate`, not always in `onNewIntent`. Disabling is irreversible-ish for a non-technical user, and IMEI-level mistakes (e.g. `com.android.providers.*`) are not recoverable from inside the app.
2. **Timeout fallthrough.** When the intent fails or the page is slow, the 3.4 s/4.2 s timers (`AutomationEngine:101`, `:167`) advance to the next package *without* pressing BACK, so the previous app's App-info page is still on screen underneath the next one. Whatever is actually visible is what gets clicked.
3. **EMUI may re-render the row after a `typeWindowContentChanged`** while the user is mid-scroll, and the first matching node can belong to a different list item.

**Fix:** verify before every destructive click. The App-info header and the action row are both reachable from the same root, and the Settings app exposes the package name in the "App info" summary (`com.android.settings:id/…`) — but the version-independent way is to carry the *expected* identity in the engine and assert it:

```java
// AutomationEngine
private String currentPkg;            // already have queue.get(currentIndex)
public synchronized String getExpectedPackage() { return running ? queue.get(currentIndex) : null; }

// AnneAccessibilityService — before clicking anything
private boolean screenMatchesPackage(AccessibilityNodeInfo root, String expectedPkg) {
    if (expectedPkg == null) return false;
    // 1) Strongest signal: any node declaring the package id
    List<AccessibilityNodeInfo> self = root.findAccessibilityNodeInfosByViewId(
            "com.android.settings:id/package_name");      // where available
    // 2) Fallback: the hierarchy must *not* mention a different tracked package
    for (String p : HuaweiCatalog.allPackages()) {
        if (p.equals(expectedPkg)) continue;
        if (!root.findAccessibilityNodeInfosByText(p).isEmpty()) return false;
    }
    return true;
}
```

Even a weaker assertion — "abort the run if the visible page does not match" — turns a silent wrong-app disable into a no-op. That is the single highest-value robustness change in this codebase.

### 1.3 The release signing key is destroyed on every build

```python
# ci_build.py:58-77
KEYSTORE_FILE = REPO_ROOT / "keystore" / "annecontrol-release.jks"
def ensure_release_keystore():
    if not KEYSTORE_FILE.exists():      # GitHub runners are ephemeral → always true
        run(["keytool", "-genkeypair", ..., "-storepass", "annecontrol2026", ...])
```

`ensure_release_keystore()` is called "persistent" in the comment, but the runner filesystem is thrown away after every job, and `dist/` + `keystore/` are not cached. So **each CI build is signed with a brand-new key**. Android refuses to install an APK whose signature differs from the installed one (`INSTALL_FAILED_UPDATE_INCOMPATIBLE`), so users who installed `latest-apk` last week cannot update — they must uninstall (losing nothing, but also losing the point of the auto-publish flow), and every build effectively invalidates the previous one.

`.gitignore` compounds it: it ignores `*.keystore`, but the file is `annecontrol-release.jks` — `git check-ignore keystore/annecontrol-release.jks` returns "not ignored". If a maintainer ever runs `python3 anne-control-apk/ci_build.py` locally, the private key lands in the repo.

**Fix:**

1. Create the keystore once, base64 it into a repo secret (`RELEASE_KEYSTORE_B64`), and restore it in CI:

```yaml
- name: Restore release keystore
  env: { KS_B64: ${{ secrets.RELEASE_KEYSTORE_B64 }} }
  run: |
    mkdir -p keystore
    echo "$KS_B64" | base64 -d > keystore/annecontrol-release.jks
```
2. Move the two passwords to `secrets.RELEASE_KEYSTORE_PASSWORD` / `RELEASE_KEY_PASSWORD` and pass them as env vars (`--ks-pass env:KS_PASS`). A signing password in a public repo is a release-integrity problem, not just cosmetics.
3. Hard-fail the build if the secret is missing, so you never silently ship an unsigned/self-signed-mismatch APK.
4. `.gitignore`: add `*.jks`, `keystore/`, `*.b64`.

---

## 2. High

### 2.1 Reported sweep numbers are invented

```java
// SystemBridge.java:270-276 — every non-protected catalog entry counts, installed or not
if (!"protected".equals(entry.tier)) { am.killBackgroundProcesses(entry.pkg); swept++; }

// :294 — "freed" is floored at 16 MB even when RAM went *down*
long freedMb = Math.max(16L, (after.availMem - before.availMem) / 1048576L);
```

`killBackgroundProcesses()` returns `void`, so there is no success signal at all; `swept` therefore counts *attempted* kills, and includes the 4 optional + ~21 safe entries **plus every third-party app installed**, whether or not it was running. `Math.max(16, …)` guarantees a positive number, so the banner always claims progress. `index.html:661` hardcodes "Swept 24 background bloat processes!" for the preview path — a number with no basis.

**Fix:** measure, don't assume.

```java
long beforeAvail = before.availMem;
int requested = 0;
for (entry : installedNonProtected) { am.killBackgroundProcesses(entry.pkg); requested++; }
// sample once more after a short settle, and report honestly
long deltaMb = (am.getMemoryInfo(after), after.availMem - beforeAvail) / 1048576L;
res.put("requestedCount", requested);
res.put("freedMb", deltaMb);        // may be 0 or negative — that is fine and informative
```

and in the UI: `"Sent stop requests to N apps · RAM delta: ±X MB"`. Users forgive "0 MB freed"; they don't forgive discovering the number is fake.

### 2.2 The RAM sweep is a global app killer

```java
// SystemBridge.java:278-290
if ((ai.flags & ApplicationInfo.FLAG_SYSTEM) == 0) {
    am.killBackgroundProcesses(p);   // ← every third-party app on the device
    swept++;
}
```

Everything non-system is killed unless its package name matches one of nine substrings (`whatsapp`, `telegram`, `gmail`, `orca`, `alarm`, `clock`, `dialer`, `contacts`, `SystemBridge:645-654`). Not covered: Signal, Viber, Slack, Outlook, any banking/2FA app, and — most visibly — **any app currently playing audio or downloading** (Spotify, a Play Store download, a WhatsApp voice note). The UI promises "keeping WhatsApp & alarms untouched" (`index.html:320`); the implementation does nothing of the sort.

This is also a Play-policy landmine if it's ever published (`KILL_BACKGROUND_PROCESSES` blanket usage).

**Fix:** invert the policy — sweep only what the user can see and reason about. The catalog already contains exactly the curated set:

```java
// 1) curated catalog only (this is what the UI is advertising anyway)
// 2) optionally: user-selected extras from a checklist
// 3) never touch: apps with a running media session, apps in UsageStatsManager
//    last-30-min bucket, any package the user marked "keep alive"
UsageStatsManager usm = ...;   // already have usage access for the cache tab
// skip if usm.queryUsageStats(BUCKET_DAILY, now-30min, now) shows it in the foreground
```

At minimum, replace the substring denylist with an explicit `KEEP_ALIVE` set in `HuaweiCatalog` and stop killing apps you know nothing about.

### 2.3 HTML injection from app labels into a `JavascriptInterface` page

```js
// index.html:746-752 (and the same pattern at :730, :807-815)
card.innerHTML =
  '<div class="pkg-head"><div><div class="pkg-name">' + item.title + '</div>' +
  '<div class="pkg-id">' + item.pkg + cacheTxt + '</div></div>' + stateBadge + '</div>' +
  '<p>' + item.desc + '</p>' + actionBtn;
```

`item.title` / `item.desc` come from a hardcoded catalog (safe today), but `ci.label` in `loadCacheList` comes from `pm.getApplicationLabel(ai)` — **arbitrary text supplied by any installed app**. A sideloaded app labelled `</div><img src=x onerror="AnneNative.startAutomation('disable','com.android.settings')">` executes with full bridge access: the bridge exposes `startAutomation`, `setCompactFontScale`, `copyToClipboard`, `openDialerCode`. Note the same file passes the *package name* into inline `onclick` handlers (`onclick="autoSingle('disable',' \(+pkg+')"`), so any future non-package identifier in that position is a second injection point.

**Fix:** stop building HTML from data. Either escape:

```js
function esc(s){ return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
```

or, better, build with DOM APIs (`textContent` for data, `addEventListener` instead of inline `onclick`), which also removes the 36 inline handlers and lets you drop any need for `unsafe-inline`-style thinking.

### 2.4 Cache scan blocks the JS thread for seconds, with no feedback

```java
// SystemBridge.java:376-402
List<ApplicationInfo> apps = pm.getInstalledApplications(0);
for (…apps…) {
    StorageStats st = ssm.queryStatsForPackage(UUID_DEFAULT, ai.packageName, myUserHandle()); // binder IPC per app
    if (cb >= 2MB) { … pm.getApplicationLabel(ai) … }
}
```

`@JavascriptInterface` methods run on the "JavaBridge" thread, but **JS is single-threaded**: `loadCacheList()` (`index.html:784`) is blocking on the return value, so the whole WebView UI freezes. On a Kirin 659, `queryStatsForPackage` costs roughly 5–20 ms per package; a P20 Lite with ~150 installed apps lands at **1–4 s of frozen UI**, on *every* visit to the Caches tab (`switchTab`, `index.html:599`) and on every Refresh. The container is blank during that time because `cacheListContainer` is only populated after the call returns.

`getHuaweiBloatListJson()` has the same shape (29 × `queryStatsForPackage`, ~0.3–0.6 s) and is called on every tab switch *and* every `refreshAll()` (`:598`, `:870`).

**Fix — async + cache + progress:**

```java
@JavascriptInterface
public void scanCachesAsync() {                 // returns immediately
    executor.execute(() -> {
        JSONObject out = scanCaches();          // existing logic, moved off the bridge thread
        postToJs("window.onCacheScan(" + out + ")");
    });
}
```
```js
function loadCacheList(){
  box.innerHTML = '<div class="card"><p>Scanning caches…</p></div>';   // spinner/skeleton
  window.AnneNative.scanCachesAsync();
}
window.onCacheScan = function(res){ /* render */ };
```

Also: cap the scan (`MATCH_USER`-style filtering — skip `FLAG_SYSTEM` apps, or only the top-N by `getAppBytes`), memoise results for ~60 s, and reuse the scan for both the Bloatware and Caches tabs so the device isn't asked twice.

### 2.5 `totalCacheMb` under-reports

```java
// SystemBridge.java:390-391
if (cb >= 2L * 1048576L) {
    totalCacheBytes += cb;     // ← only apps ≥2 MB are accumulated
```

The header says "Reclaimable Cache: X MB" but X excludes the long tail of sub-2 MB caches, which on a 150-app phone is easily 100–300 MB. Either accumulate into a separate `allCacheBytes` before the `if`, or label the number "in apps with ≥2 MB cache".

### 2.6 Timeouts pose as success

```java
// AutomationEngine.java:43-50
private final Runnable timeoutRunnable = () -> { if (!running) return; advanceToNextPackage(); };
// :97-103  every step transition re-arms it with 3.4s
// :167     and the first page gets 4.2s
```

Three problems:

* **Silent abandonment.** If the storage page hasn't rendered in 3.4 s (common on eMMC 5.1 with a cold Settings process), `handleClearCache` never executes → the cache is not cleared, nothing is reported, and `advanceToNextPackage()` moves on.
* **Success inflation.** `markPackageSuccessAndAdvance()` increments `succeededCount` on `performAction(ACTION_CLICK) == true` (`AnneAccessibilityService:129`, `:184`, `:206`). `performAction` returning `true` only means "the click was dispatched", not that the app was stopped or the cache cleared. Clicking a disabled/greyed row that is technically clickable inflates the count.
* **Wrong-screen risk.** On the force-stop path, if the button is disabled the code just advances (`:110-113`) **without** `GLOBAL_ACTION_BACK`, leaving the page open for the next intent (feeds 1.2).

**Fix:** model three outcomes — `SUCCESS`, `SKIPPED_ALREADY_DONE`, `FAILED_TIMEOUT` — retry once with a longer window before declaring timeout, always `performGlobalAction(BACK)` before navigating away, and show the breakdown at the end ("14 disabled · 6 not installed · 2 timed out") instead of one number.

---

## 3. Medium

### 3.1 `startAutomation` results are ignored by every caller

`autoSingle` (`index.html:761`), `autoRunSafeBloat` (`:765`), `autoCleanTopCaches` (`:821`) discard the JSON `startAutomation` returns. When it says `{"ok":false,"needsAccessibility":true}` the user gets a toast *and* a Settings screen pushed at them, then is returned to a UI that looks like nothing happened. Parse the result and render it.

### 3.2 `start()` while running can wedge the engine and skip a package

`start()` (`AutomationEngine:52-74`) clears `queue`, resets `currentIndex = 0`, and sets `running = true` — but it does **not** `handler.removeCallbacks(...)` for the pending `openCurrentPackageSettings` runnable posted by `advanceToNextPackage` (`:146-151`). That stale runnable then opens `queue.get(currentIndex)` of the *new* run a second time, and the engine's index/step no longer correspond to what's on screen. Add a generation counter:

```java
private int generation = 0;
public synchronized void start(...) { generation++; handler.removeCallbacksAndMessages(null); ... }
private synchronized void openCurrentPackageSettings() { final int g = generation; ... if (g != generation) return; }
```

### 3.3 Confirm-dialog detection can re-click the action button

```java
// AnneAccessibilityService.java:41-44
LABELS_CONFIRM = { "ok", "force stop", "disable", "disable app", "yes", … }
```

Deliberately overlapping with `LABELS_FORCE_STOP` / `LABELS_DISABLE`. At `STEP_WAIT_CONFIRM_DIALOG`, if no dialog is present (or `android:id/button1` isn't found, which happens with EMUI's custom dialogs), `findDialogConfirmButton` falls through to `findClickableByLabels(root, LABELS_CONFIRM, true)` and **clicks the underlying action button again**, then reports success (`performAction` returns `true` for the already-pressed row), which also inflates `succeededCount`.

Search should be scoped to the dialog. An `AlertDialog` is its own window, so the reliable discriminator is window identity, not window type (an in-app dialog still reports `TYPE_APPLICATION`):

```java
// dialog nodes live in a different window than the page root
AccessibilityWindowInfo pageWin = root.getWindow();          // API 21+
...
AccessibilityWindowInfo nodeWin = candidate.getWindow();
boolean inDialog = nodeWin != null && pageWin != null
        && nodeWin.getId() != pageWin.getId();
```

`getRootInActiveWindow()` already returns the topmost *focused* window, so an alternative one-liner is to only consider the root whose window differs from the one the App-info page was found in — but simply requiring `android:id/button1` plus one of the neutral labels (`ok`, `yes`, `ja`, `oui`, `sí`, `موافق`) and **excluding** anything matching the action label is the low-risk version. Either way, `LABELS_CONFIRM` should not contain `"force stop"` / `"disable"`; the action label is already known from the step that opened the dialog, so pass it explicitly instead of widening a global list.

### 3.4 Accessibility tree is traversed up to 9 times per event

`findClickableByLabels` (`:246-273`) calls `root.findAccessibilityNodeInfosByText(target)` once per alias, and every call walks the whole window (Settings trees are 100–400 nodes deep with `flagIncludeNotImportantViews`). With `notificationTimeout="120"` and `typeWindowContentChanged` in the config, a scrolling Settings page can deliver ~8 events/s → on the order of **70 full tree walks per second** on a Kirin 659, exactly while the automation is driving that UI. Two cheap wins:

* single pass: walk `root` once with `AccessibilityNodeInfo` children recursion, collecting text→node matches for all aliases;
* raise `notificationTimeout` to 250–300 and drop `typeWindowContentChanged` to `typeWindowStateChanged` if you can live with slightly slower reaction;
* early-return before `getRootInActiveWindow()` when `step == STEP_IDLE` or the throttle window hasn't elapsed (currently the throttle check happens *before* the root fetch — good — but the root is still fetched for every event that passes the 280 ms gate even when nothing can match).

### 3.5 Dead permissions and a misleading ADB instruction

`AndroidManifest.xml:11-19` declares `WRITE_SECURE_SETTINGS` and `GET_PACKAGE_SIZE`, neither of which appears anywhere in the Java sources (`WRITE_SECURE_SETTINGS` is not grantable from the manifest — it is `signature|privileged` and only reachable via `pm grant`). Meanwhile `index.html:526` tells the user to run:

```
adb shell pm grant com.annecontrol.p20lite android.permission.WRITE_SECURE_SETTINGS
```

…and the app never uses it. Either implement the Secure-settings features that need it (e.g. `Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES` self-enable — which would also fix 1.1) or remove both the permission and the instruction. Also: `android:allowBackup="true"` on a system-tuning app should be `false` (it exports the app's data via ADB backup for no benefit), and `PACKAGE_USAGE_STATS` should carry `tools:ignore="ProtectedPermissions"` so lint doesn't drown the signal.

### 3.6 CI/release engineering

| Issue | Detail | Fix |
|---|---|---|
| No `concurrency` | Two pushes in quick succession run two jobs that both `tag_name: latest-apk` → the second gets `422 already_exists` or silently overwrites the release asset mid-download | add `concurrency: {group: apk-${{ github.ref }}, cancel-in-progress: true}` |
| Publishing from `arena/**` | Every feature-branch push moves the public `latest-apk` tag and downloads a possibly-broken build | publish only on `main` (or gate behind a `v*` tag), keep `arena/**` as artifact-only |
| Lexicographic tool pick | `sorted((sdk_root/"build-tools").iterdir())[-1]` picks `"9.0.0"` over `"34.0.0"`; same for `platforms/` (`"android-9"` > `"android-28"` lexicographically) | sort with a version key: `sorted(dirs, key=lambda p: [int(x) for x in re.findall(r"\d+", p.name)])` |
| No friendly failure | `(sdk_root/"build-tools").iterdir()` raises `FileNotFoundError` before the nice `sys.exit("ERROR: No build-tools…")` can run | guard with `if not d.exists()` |
| Secrets in source | `-storepass annecontrol2026` twice in `ci_build.py` | env vars / `--ks-pass env:KS_PASS` |
| No lint/tests in CI | The pipeline compiles and signs, but nothing checks behaviour | see §6 |

### 3.7 `minSdk 24` vs `StorageStatsManager` (API 26)

`SystemBridge` imports `android.app.usage.StorageStats` / `StorageStatsManager` at class level and guards every *use* with `SDK_INT >= 26` — correct, but on API 24/25 devices the class verifier can fail at load time depending on ART's verification mode (`NoClassDefFoundError` on first touch of `SystemBridge`, i.e. on the very first dashboard call). Two options: raise `minSdk` to 26 (the app is explicitly for ANE-LX1 on EMUI 9.1 = API 28, so 26 costs nothing), or move all 26+ code into a `StorageStats26` helper instantiated behind the version check. I'd raise `minSdkVersion` to 26 and delete the guards — a P20 Lite on EMUI 9.1 is API 28.

---

## 4. Low / polish

* **`index.html:438`** — `<div class=card …>` unquoted attribute (works, but it's the one place inconsistent with the rest of the file).
* **`index.html:5`** — `maximum-scale=1.0, user-scalable=no` on an app that is literally an accessibility tool. Let users zoom.
* **`index.html:576-581`** — `showBanner` never cancels the previous `setTimeout`; a fast second banner gets hidden by the first banner's timer. Keep the handle and `clearTimeout` it.
* **`index.html:655-670`** — `runRamSweep` sets the button text and *then* calls the bridge; if `JSON.parse` throws (or the bridge throws), the label stays "Sweeping…" forever. Wrap in `try/catch/finally`.
* **`index.html:781-819`** — `cacheItems` is not cleared on the `needsUsageAccess` branch, so `autoCleanTopCaches` (`:823`) can act on **stale** packages after usage access was revoked.
* **`index.html:710-755`** — full re-render on every keystroke (`oninput="filterBloatSearch()"`), rebuilding up to 29 cards with `innerHTML` and 29 `appendChild` calls. Debounce ~150 ms and build into a `DocumentFragment`.
* **`index.html`** — emoji-only iconography with no `aria-label`s, no `:focus-visible` styles, and `user-select:none` globally (a11y). Also `backdrop-filter: blur(10px)`/`(12px)` on the sticky topbar and fixed bottom nav is a real, continuous GPU cost on a Mali-T830 — remove it for the "performance" story.
* **`SystemBridge:207-252`** — `cachedBattery` + `lastBatteryFetchTime` are read/written from the JS bridge thread pool without `synchronized`/`volatile`; harmless today (the worst case is a duplicate read) but it's a latent race if you ever touch it from the main thread. Same for `cachedBattery` being returned by reference.
* **`SystemBridge:404-411`** — the `Comparator` works but `return (int) Long.compare(b.cacheBytes, a.cacheBytes)` is clearer and immune to future overflow edits.
* **`SystemBridge:480-496`** — `Float.parseFloat("NaN")` passes both clamps (`NaN < 0.80f` is `false`), and `Settings.System.putFloat` return value is ignored. Validate `Float.isNaN/isInfinite` and check the boolean. Also: writing `Settings.System.FONT_SCALE` directly does not reliably take effect without a configuration change/reboot on AOSP-derived ROMs — tell the user, or listen for `ACTION_CONFIGURATION_CHANGED` and confirm the value stuck.
* **`AnneAccessibilityService:302-318`** — `resolveClickableParent` silently gives up past depth 5; on EMUI rows the clickable ancestor is often the `LinearLayout` 2–3 levels up, so 5 is fine, but log/telemetry-free failure means a "nothing happened" bug is invisible. Consider matching `isClickable() || isCheckable()` too.
* **`AnneAccessibilityService:229-244`** — `isForbiddenLabel` uses `contains("delete")` and `contains("reset")`; combined with `findAccessibilityNodeInfosByText` substring matching, an innocent label like "Reset app preferences" (a *different* row on the same screen) is filtered — that's the safe direction, but the check also runs on the **cache-clear** path where "Clear data" and "Clear cache" live one row apart, so a mis-`startsWith` match is what protects you. Prefer exact-match against a known-safe label set here, and add the storage page's "Clear data" translations you're missing (TR/PL/JA/ID/VI are common on EMUI).
* **`MainActivity`** — no `onDestroy()` → `webView.destroy()`; no `onSaveInstanceState`/`restoreState` (relates to the "prevent background reloads" goal: if EMUI does kill the process you can at least restore the tab). `launchMode="singleTask"` + `CLEAR_TOP` in `returnToApp` is right.
* **`AutomationEngine:76-83`** — the `return;` at the end of a `void` method and the "Automation finished (" + succeededCount + " processed)" message on a *user-initiated* cancel are both confusing; distinguish cancel from completion.
* **`AutomationEngine:105-110`** — `getCurrentPackage()` returns `""` once `running` flips false, so the UI can never show the last processed package.
* **`AutomationEngine:150-171`** — magic constants `380`, `3400`, `4200`, `280` scattered across three files; hoist them into one `Timings` class so they can be tuned per device.
* **`HuaweiCatalog`** — no duplicate package names (verified: 29 entries = 21 `safe` + 4 `optional` + 4 `protected`), and `isProtected()` correctly skips the protected tier in the sweep. But the sweep treats `optional` the same as `safe` (`SystemBridge:272` only skips `"protected"`), so `com.huawei.appmarket`, `com.huawei.hicloud`, `com.huawei.health` and `com.huawei.wallet` — the ones whose own descriptions say "keep only if you pair a Huawei Watch/Band" — get killed by a button labelled "Sweep Background Bloat". Gate the sweep on `"safe".equals(entry.tier)` and keep `optional` behind explicit user selection.
* **Localisation** — the UI is 100% English while the accessibility labels are 8 languages. Either translate the UI or drop the multilingual claim; and the Arabic/Russian labels are dead weight on EMEA `ANE-LX1` firmware unless the aliases are verified against an actual device dump. A `strings.xml` extraction plus a small table (`res/values-de/strings.xml`) would fix this properly — and label lookup could then read the `Button`'s resource name instead of guessing text.

---

## 5. Performance summary (what to fix first, with expected effect)

| Action | Cost today | After |
|---|---|---|
| Remove `backdrop-filter` from topbar + bottom nav | continuous GPU compositing during every scroll on Mali-T830 | one-line CSS delete |
| Make `getTopCacheAppsJson`/`getHuaweiBloatListJson` async + cached | 1–4 s frozen UI per tab visit, twice per refresh | <16 ms to first paint, background work |
| One-pass node matching in `findClickableByLabels` | up to ~70 full tree walks/s while automating | ~8 walks/s |
| `notificationTimeout` 120 → 260 | event storm during Settings scroll | ~2× fewer callbacks |
| Scope `sweepBackgroundRamJson` to the curated catalog | 25–200 binder `killBackgroundProcesses` calls + `getInstalledApplications(0)` (~0.3 s) | 21 calls, no enumerate |
| Debounce the bloat search + `DocumentFragment` | 29-card `innerHTML` rebuild per keystroke | ~1 rebuild per query |

---

## 6. Testing & maintainability (the structural gap)

There is **no test of any kind**, and the most bug-prone code is the least testable. The good news: `AutomationEngine`'s *policy* is almost pure — extract it and it becomes trivially unit-testable on the JVM with no emulator:

```java
// new: pure, no Handler / no Context
final class QueuePlanner {
    enum Outcome { SUCCESS, ALREADY_DONE, FAILED }
    QueuePlanner(List<String> pkgs, boolean skipProtected) { … }
    String current(); int index(); int total();
    Result advance(Outcome o);          // Result = {next pkg | finished, successCount, failCount}
    Snapshot snapshot();
}
```

Then `AutomationEngine` becomes a thin `Handler` wrapper around it, and you can write JVM tests for: protected-package filtering, empty queue, `clear_cache` including protected packages, index bounds, cancel-mid-run, and the 3.2 stale-runnable case. Add a second test that validates `HuaweiCatalog` (no duplicate package names, every `tier` ∈ {safe, optional, protected}, every `protected` entry is `isProtected`), and the cost is an afternoon.

CI additions worth having: `javac -Xlint:all -Werror` (currently `-Xlint:none` at `ci_build.py:112`), `python3 -m py_compile`, a JSON round-trip check for the four `*Json()` methods, and artifact retention 90 → 14 days (a 3 MB APK × 90 days × every push adds up).

---

## 7. Suggested order of work

1. **1.3** persistent signing key + move secrets out of the repo — without this, every release you publish is a dead end for users who already installed.
2. **1.1** stop path (notification/volume key) + require `isServiceConnected()` — turns an unescapable automation into a controllable one.
3. **1.2** verify the on-screen package before every destructive click — turns "disabled the wrong app" into "skipped".
4. **2.1/2.2** honest metrics + an allowlist-based sweep — the two claims users can verify on their own phone in 10 seconds.
5. **2.4/2.5** async, cached, complete cache scan + loading state — the biggest perceived-speed win.
6. **2.3** escape/avoid `innerHTML` — cheap, removes the only path from untrusted text to a native bridge.
7. **2.6/3.2/3.3** outcome modelling, generation token, scoped confirm search — makes the automation debuggable instead of mysterious.
8. **3.6/§6** CI hygiene + the `QueuePlanner` extraction and its tests.

---

## Appendix A — small patches worth applying as-is

```python
# ci_build.py — version-aware tool selection + friendly failure
def _ver_key(p: Path):
    return [int(x) for x in re.findall(r"\d+", p.name)] or [0]

bt_root = sdk_root / "build-tools"
if not bt_root.is_dir():
    sys.exit(f"ERROR: {bt_root} is missing — install build-tools via sdkmanager")
bt = sorted((d for d in bt_root.iterdir() if d.is_dir()), key=_ver_key)[-1]
```

```xml
<!-- accessibility_service_config.xml — fewer events, no package-name trap -->
android:notificationTimeout="260"
android:accessibilityEventTypes="typeWindowStateChanged"
android:accessibilityFlags="flagDefault|flagReportViewIds|flagIncludeNotImportantViews|flagRequestFilterKeyEvents"
android:canRequestFilterKeyEvents="true"
<!-- drop android:packageNames: the Java code already checks the package, and
     the filter hides any Settings screen hosted outside com.android.settings -->
```

```js
// index.html — banner timer race
var bannerTimer = null;
function showBanner(msg) {
  var el = document.getElementById("statusToast");
  el.textContent = msg; el.style.display = "block";
  if (bannerTimer) clearTimeout(bannerTimer);
  bannerTimer = setTimeout(function(){ el.style.display = "none"; bannerTimer = null; }, 5500);
}
```

```xml
<!-- AndroidManifest.xml -->
android:allowBackup="false"
android:versionCode="102"   <!-- bump with every published build -->
```

---

*Reviewed files:* `AndroidManifest.xml` (52 L), `res/xml/accessibility_service_config.xml` (9 L), `MainActivity.java` (68 L), `SystemBridge.java` (688 L), `AnneAccessibilityService.java` (323 L), `AutomationEngine.java` (182 L), `HuaweiCatalog.java` (97 L), `assets/index.html` (889 L), `ci_build.py` (180 L), `build-annecontrol-apk.yml` (57 L). No tests exist in the repository.

---

## 8. Fix status (branch `arena/eeb27ed3-reviewer-b`)

Implemented in 1.0.2 (`versionCode 102`):

| Finding | Status | What changed |
|---|---|---|
| 1.1 No way to cancel / false-positive service check | ✅ Fixed | `hasAccessibilityEnabled()` now requires a live binding; `onDestroy` clears the flag; ongoing notification with a **STOP** action (`StopAutomationReceiver`) updated per package, plus a Volume Down hook in the service; a "switched on but not running (EMUI killed it)" state is surfaced instead of starting a dead run |
| 1.2 Clicking without verifying the target app | ✅ Fixed | Engine resolves each package's label; the service verifies label/package text in the window before any destructive click and aborts the run after 4 unexplained mismatches |
| 1.3 Signing key regenerated every build | ✅ Fixed | `RELEASE_KEYSTORE_B64` secret restored in CI, passwords via `env:` (never on the command line), loud `::warning::` when a throwaway key is used, `*.jks`/`keystore/`/`*.b64` git-ignored, setup documented in `README.md` |
| 2.1 Fabricated sweep metrics | ✅ Fixed | Reports `requestedCount` + real measured delta (may be 0/negative); preview banner no longer invents "24" |
| 2.2 Global app killer with a hidden messaging denylist | ✅ Fixed | User-controlled Keep Alive list (empty by default), sweep scope toggle, curated sweep limited to the `safe` tier; `isImportantMessagingApp()` deleted — WhatsApp is killable, as requested |
| 2.3 `innerHTML` injection from app labels | ✅ Fixed | All list rendering rebuilt with `textContent` + `addEventListener`; verified by executing the real page under jsdom with a hostile app label |
| 2.4 Blocking cache scan, no feedback | ✅ Fixed | Scan now runs on a background executor (`scanCachesAsync`/`scanBloatListAsync`) and streams `window.onScanProgress` ("Scanning… 8 of 150 apps") before calling back with `window.onCacheScan`. System packages skipped, results memoised for 25 s; the blocking bridge call is no longer on the UI path |
| 2.5 `totalCacheMb` under-count | ✅ Fixed | Total now accumulates every scanned app; list still gated at 2 MB |
| 2.6 Timeouts posing as success | ◐ Mostly fixed | `SUCCESS`/`SKIPPED`/`FAILED` outcomes with separate counters; BACK is pressed before navigating; the summary reports the breakdown instead of one number. Still open: a successful `ACTION_CLICK` is counted as success even when the ROM does not show a confirmation dialog |
| 3.1 Ignored `startAutomation` result | ✅ Fixed | `startAutomation()` JSON is parsed; "nothing was started" is shown when the service is not running |
| 3.2 `start()` mid-run skipping a package | ✅ Fixed | `generation` token invalidates callbacks from a previous run |
| 3.3 Confirm labels overlapping action labels | ✅ Fixed | `android:id/button1` → neutral wording → mode-specific wording, in that order; action labels removed from the neutral list |
| 3.4 Tree walked once per label per event | ✅ Fixed | One bounded breadth-first walk per query (`scanTree`, 900-node cap) replaces one native subtree search per alias; content descriptions are matched too. `notificationTimeout` 120 → 260 ms, early return on `STEP_IDLE`, `packageNames` filter dropped. Per event: ~2 walks instead of up to 10 |
| 3.5 Dead permissions / misleading ADB claim | ✅ Fixed | `WRITE_SECURE_SETTINGS` + `GET_PACKAGE_SIZE` removed from the manifest, Power-tab command now the real `appops` grant, `allowBackup="false"` |
| 3.6 CI hygiene | ✅ Fixed | `concurrency` group, release published only from `main`, version-aware tool sorting, friendly SDK errors, `-Xlint:all,-options` warnings printed |
| 3.7 `minSdk 24` vs `StorageStatsManager` | ✅ Fixed | `minSdkVersion` 26 in manifest and build script |
| §4 Low/polish (banner timer, stuck button, stale `cacheItems`, NaN clamp, `putFloat` result, zoom, backdrop blur, unquoted attribute) | ✅ Fixed | See `index.html`, `SystemBridge.setCompactFontScale` |
| §6 No tests | ✅ Fixed | `QueuePlanner` extraction (no Android imports) with plain-JVM tests in `test/java/`, executed by `ci_build.py` before the APK is built — a failing assertion fails the build. The WebView page is covered by `test/ui/` (jsdom, 41 assertions: injection safety, honest reporting, keep-alive persistence, async progress, failure surfacing, both cancel paths), run as its own CI step |
| §4 Localisation | ◐ Partial | The strings users see in Android's own UI (app name, accessibility service label + consent description) are now translated into DE/ES/FR/PT under `res/values-*/`. The WebView UI itself is still English-only — a full HTML translation is the remaining piece |
| §4 Debounced bloat search, single-pass verification text search | ⬜ Open | Search still re-renders on every keystroke (now with a DocumentFragment, so it is cheap); verification still uses one normalised text walk per event, which is already bounded |


---

## 9. Second pass (same branch)

Additional work after the first fix round:

* **Async cache scan with progress** — `scanCachesAsync()` / `scanBloatListAsync()` run on a single-thread executor; progress and results come back through `window.onScanProgress` / `window.onCacheScan` / `window.onBloatScan`. The `@JavascriptInterface` blocking path is kept only for the explicit Auto-Clean button, which now also goes through the scan callback via a `pendingAutoClean` flag.
* **Single-pass accessibility traversal** — `scanTree()` + `NodeVisitor`, bounded to 900 nodes, replacing per-alias native searches.
* **`QueuePlanner`** — queue filtering, ordering, outcome counters and summary text moved out of `AutomationEngine` into a pure-Java class, covered by `test/java/.../QueuePlannerTest.java` (22 assertions) that `ci_build.py` compiles and runs on a plain JVM before building. The engine now delegates, so `start()`/`advance`-related regressions (duplicates, protected-package filtering, overrun past the queue, unknown outcomes) are caught without a device.
* **UI regression suite** — `test/ui/ui_test.js` runs the real `index.html` under jsdom against a stub bridge; `test/ui/package.json` pins jsdom. Wired in as its own workflow step.
* **Localisation** — `res/values-de|es|fr|pt/strings.xml` for the accessibility service label and consent description (what a non-English user reads before granting the permission).
