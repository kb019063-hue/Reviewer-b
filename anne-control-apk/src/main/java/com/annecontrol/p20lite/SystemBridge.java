package com.annecontrol.p20lite;

import android.app.Activity;
import android.app.ActivityManager;
import android.app.AppOpsManager;
import android.app.usage.StorageStats;
import android.app.usage.StorageStatsManager;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.ComponentName;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.BatteryManager;
import android.os.Build;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.os.StatFs;
import android.os.storage.StorageManager;
import android.provider.Settings;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.FileReader;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class SystemBridge {

    private final Context ctx;
    private final Activity activity;
    private final WebView webView;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final ExecutorService scanExecutor = Executors.newSingleThreadExecutor();

    // Battery status caching to eliminate redundant IPC calls
    private long lastBatteryFetchTime = 0L;
    private JSONObject cachedBattery = null;

    // Memoised StorageStats scans; see invalidateScanCaches()
    private static final long SCAN_CACHE_MS = 25000L;
    private long lastBloatScanTime = 0L;
    private long lastCacheScanTime = 0L;
    private String cachedBloatJson = null;
    private String cachedCacheJson = null;
    private boolean cachedBloatStatsState = false;

    public SystemBridge(Activity activity, WebView webView) {
        this.activity = activity;
        this.ctx = activity.getApplicationContext();
        this.webView = webView;
    }

    private boolean isSupportedDevice() {
        String model = Build.MODEL == null ? "" : Build.MODEL.toUpperCase(java.util.Locale.US);
        return "HUAWEI".equalsIgnoreCase(Build.MANUFACTURER)
                && model.contains("ANE-LX1")
                && Build.VERSION.SDK_INT == 28;
    }

    public boolean hasUsageAccess() {
        try {
            AppOpsManager appOps = (AppOpsManager) ctx.getSystemService(Context.APP_OPS_SERVICE);
            if (appOps == null) return false;
            int mode = appOps.checkOpNoThrow(
                    AppOpsManager.OPSTR_GET_USAGE_STATS,
                    android.os.Process.myUid(),
                    ctx.getPackageName()
            );
            return mode == AppOpsManager.MODE_ALLOWED;
        } catch (Exception e) {
            return false;
        }
    }

    public boolean hasWriteSettings() {
        try {
            return Settings.System.canWrite(ctx);
        } catch (Exception e) {
            return false;
        }
    }

    /**
     * True only when the service is actually bound right now.
     *
     * The old implementation also accepted "our package is listed in
     * ENABLED_ACCESSIBILITY_SERVICES". That is a persisted preference: EMUI's own
     * battery manager routinely kills the service while the preference still lists
     * it, so the app would start a run that could never click anything, and the
     * user could not reach the in-app cancel because Settings was on top.
     */
    public boolean hasAccessibilityEnabled() {
        return AnneAccessibilityService.isServiceConnected();
    }

    /** Whether the user has flipped the Accessibility switch at all (diagnostics only). */
    public boolean isAccessibilityListedInSettings() {
        try {
            String enabled = Settings.Secure.getString(
                    ctx.getContentResolver(),
                    Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
            );
            return enabled != null && enabled.contains(ctx.getPackageName());
        } catch (Exception e) {
            return false;
        }
    }

    public boolean hasBatteryExemption() {
        try {
            PowerManager pm = (PowerManager) ctx.getSystemService(Context.POWER_SERVICE);
            return pm != null && pm.isIgnoringBatteryOptimizations(ctx.getPackageName());
        } catch (Exception e) {
            return false;
        }
    }

    @JavascriptInterface
    public String getDashboardJson() {
        try {
            JSONObject root = new JSONObject();

            // Hardware & Build info
            root.put("model", Build.MODEL != null ? Build.MODEL : "Unknown");
            root.put("supportedDevice", isSupportedDevice());
            root.put("manufacturer", Build.MANUFACTURER != null ? Build.MANUFACTURER : "HUAWEI");
            root.put("displayBuild", Build.DISPLAY != null ? Build.DISPLAY : "EMUI 9.1");
            root.put("hardware", Build.HARDWARE != null ? Build.HARDWARE : "hi6250");
            root.put("androidRelease", Build.VERSION.RELEASE != null ? Build.VERSION.RELEASE : "9");
            root.put("sdkInt", Build.VERSION.SDK_INT);
            root.put("securityPatch", Build.VERSION.SECURITY_PATCH != null ? Build.VERSION.SECURITY_PATCH : "Unknown");

            // Permissions
            JSONObject perms = new JSONObject();
            perms.put("usageAccess", hasUsageAccess());
            perms.put("accessibility", hasAccessibilityEnabled());
            // Switched on in Settings but not currently bound (EMUI killed it).
            perms.put("accessibilityStale",
                    !hasAccessibilityEnabled() && isAccessibilityListedInSettings());
            perms.put("writeSettings", hasWriteSettings());
            perms.put("batteryExemption", hasBatteryExemption());
            root.put("permissions", perms);

            // RAM via ActivityManager + /proc/meminfo
            ActivityManager am = (ActivityManager) ctx.getSystemService(Context.ACTIVITY_SERVICE);
            ActivityManager.MemoryInfo mi = new ActivityManager.MemoryInfo();
            if (am != null) {
                am.getMemoryInfo(mi);
            }
            long totalMb = mi.totalMem > 0 ? (mi.totalMem / 1048576L) : 3768L;
            long availMb = mi.availMem > 0 ? (mi.availMem / 1048576L) : 1100L;
            long swapTotalMb = 0L;
            long swapFreeMb = 0L;
            long cachedMb = 0L;

            BufferedReader br = null;
            try {
                br = new BufferedReader(new FileReader("/proc/meminfo"));
                String line;
                while ((line = br.readLine()) != null) {
                    if (line.startsWith("Cached:")) {
                        cachedMb = parseKbLineToMb(line);
                    } else if (line.startsWith("SwapTotal:")) {
                        swapTotalMb = parseKbLineToMb(line);
                    } else if (line.startsWith("SwapFree:")) {
                        swapFreeMb = parseKbLineToMb(line);
                    }
                }
            } catch (Exception ignored) {
            } finally {
                if (br != null) {
                    try { br.close(); } catch (Exception ignored) {}
                }
            }

            JSONObject ram = new JSONObject();
            ram.put("totalMb", totalMb);
            ram.put("availMb", availMb);
            ram.put("usedMb", Math.max(0L, totalMb - availMb));
            ram.put("cachedMb", cachedMb);
            ram.put("swapTotalMb", swapTotalMb);
            ram.put("swapUsedMb", Math.max(0L, swapTotalMb - swapFreeMb));
            ram.put("lowMemory", mi.lowMemory);
            root.put("ram", ram);

            // Storage (/data eMMC 5.1 check)
            StatFs statFs = new StatFs(Environment.getDataDirectory().getPath());
            long totalBytes = statFs.getTotalBytes();
            long availBytes = statFs.getAvailableBytes();
            long usedBytes = Math.max(0L, totalBytes - availBytes);
            double totalGb = round1(totalBytes / 1073741824.0);
            double freeGb = round1(availBytes / 1073741824.0);
            double usedGb = round1(usedBytes / 1073741824.0);
            int pctUsed = totalBytes > 0 ? (int) Math.round((usedBytes * 100.0) / totalBytes) : 0;

            JSONObject storage = new JSONObject();
            storage.put("totalGb", totalGb);
            storage.put("freeGb", freeGb);
            storage.put("usedGb", usedGb);
            storage.put("percentUsed", pctUsed);
            root.put("storage", storage);

            // Battery (cached for 3 seconds to reduce binder IPC overhead)
            root.put("battery", getBatteryInfoJson());

            // Current Settings
            ContentResolver cr = ctx.getContentResolver();
            float fontScale = Settings.System.getFloat(cr, Settings.System.FONT_SCALE, 1.0f);
            float winAnim = Settings.Global.getFloat(cr, Settings.Global.WINDOW_ANIMATION_SCALE, 1.0f);
            int timeoutMs = Settings.System.getInt(cr, Settings.System.SCREEN_OFF_TIMEOUT, 60000);

            JSONObject sysSet = new JSONObject();
            sysSet.put("fontScale", round2(fontScale));
            sysSet.put("windowAnimScale", round2(winAnim));
            sysSet.put("screenTimeoutSec", Math.round(timeoutMs / 1000f));
            root.put("settings", sysSet);

            return root.toString();
        } catch (Exception e) {
            return "{\"error\":\"" + safeJson(e.getMessage()) + "\"}";
        }
    }

    /**
     * A local, user-initiated troubleshooting report. Deliberately excludes
     * Android ID, serial/IMEI, contacts, user files, and the installed-app list.
     */
    @JavascriptInterface
    public String getSupportReportJson() {
        try {
            JSONObject root = new JSONObject();
            JSONObject device = new JSONObject();
            device.put("manufacturer", Build.MANUFACTURER == null ? "Unknown" : Build.MANUFACTURER);
            device.put("model", Build.MODEL == null ? "Unknown" : Build.MODEL);
            device.put("brand", Build.BRAND == null ? "Unknown" : Build.BRAND);
            device.put("product", Build.PRODUCT == null ? "Unknown" : Build.PRODUCT);
            device.put("androidRelease", Build.VERSION.RELEASE == null ? "Unknown" : Build.VERSION.RELEASE);
            device.put("sdkInt", Build.VERSION.SDK_INT);
            device.put("emuiBuild", Build.DISPLAY == null ? "Unknown" : Build.DISPLAY);
            device.put("buildFingerprint", Build.FINGERPRINT == null ? "Unknown" : Build.FINGERPRINT);
            device.put("securityPatch", Build.VERSION.SECURITY_PATCH == null ? "Unknown" : Build.VERSION.SECURITY_PATCH);
            device.put("supportedAutomationTarget", isSupportedDevice());
            root.put("device", device);

            JSONObject app = new JSONObject();
            try {
                android.content.pm.PackageInfo own = ctx.getPackageManager().getPackageInfo(ctx.getPackageName(), 0);
                app.put("versionName", own.versionName == null ? "Unknown" : own.versionName);
                app.put("versionCode", Build.VERSION.SDK_INT >= 28 ? own.getLongVersionCode() : own.versionCode);
            } catch (Exception ignored) {
                app.put("versionName", "Unknown");
            }
            app.put("packageName", ctx.getPackageName());
            app.put("internetPermissionDeclared", ctx.getPackageManager().checkPermission(
                    "android.permission.INTERNET", ctx.getPackageName()) == PackageManager.PERMISSION_GRANTED);
            root.put("app", app);

            JSONObject access = new JSONObject();
            access.put("accessibilityServiceConnected", hasAccessibilityEnabled());
            access.put("accessibilityListedInSettings", isAccessibilityListedInSettings());
            access.put("usageAccess", hasUsageAccess());
            access.put("modifySystemSettings", hasWriteSettings());
            access.put("batteryOptimizationExemption", hasBatteryExemption());
            root.put("access", access);

            String themesPackage = null;
            String themesVersion = null;
            String[] candidates = {"com.huawei.android.thememanager", "com.android.thememanager"};
            for (String candidate : candidates) {
                try {
                    android.content.pm.PackageInfo info = ctx.getPackageManager().getPackageInfo(candidate, 0);
                    themesPackage = candidate;
                    themesVersion = info.versionName;
                    break;
                } catch (Exception ignored) {
                }
            }
            JSONObject themes = new JSONObject();
            themes.put("managerInstalled", themesPackage != null);
            themes.put("managerPackage", themesPackage == null ? "Not detected" : themesPackage);
            themes.put("managerVersion", themesVersion == null ? "Unknown" : themesVersion);
            if (activity instanceof MainActivity) {
                try {
                    themes.put("lastInspection", new JSONObject(((MainActivity) activity).getLastThemeInspectionJson()));
                } catch (Exception ignored) {
                }
            }
            root.put("themes", themes);
            root.put("privacy", "Created on-device. No report is sent automatically. No serial, IMEI, Android ID, contacts, personal files, or installed-app list is included. Review before sharing.");
            return root.toString(2);
        } catch (Exception e) {
            return "{\"error\":\"" + safeJson(e.getMessage()) + "\"}";
        }
    }

    private JSONObject getBatteryInfoJson() {
        long now = System.currentTimeMillis();
        if (cachedBattery != null && (now - lastBatteryFetchTime < 3000L)) {
            return cachedBattery;
        }

        int level = 100;
        double tempC = 30.0;
        int voltageMv = 4000;
        String source = "On Battery";
        String healthStr = "Good";

        try {
            Intent batIntent = ctx.registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
            if (batIntent != null) {
                int lv = batIntent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
                int sc = batIntent.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
                if (lv >= 0 && sc > 0) {
                    level = Math.round((lv * 100f) / sc);
                }
                int t = batIntent.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 300);
                tempC = round1(t / 10.0);
                voltageMv = batIntent.getIntExtra(BatteryManager.EXTRA_VOLTAGE, 4000);
                int plugged = batIntent.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0);
                if (plugged == BatteryManager.BATTERY_PLUGGED_AC) source = "Fast Wall Charger (AC)";
                else if (plugged == BatteryManager.BATTERY_PLUGGED_USB) source = "USB Cable";
                int h = batIntent.getIntExtra(BatteryManager.EXTRA_HEALTH, BatteryManager.BATTERY_HEALTH_GOOD);
                if (h == BatteryManager.BATTERY_HEALTH_OVERHEAT) healthStr = "Warm / Overheat";
                else if (h == BatteryManager.BATTERY_HEALTH_DEAD) healthStr = "Worn / Replace Soon";
            }
        } catch (Exception ignored) {
        }

        JSONObject bat = new JSONObject();
        try {
            bat.put("level", level);
            bat.put("tempC", tempC);
            bat.put("voltageMv", voltageMv);
            bat.put("source", source);
            bat.put("health", healthStr);
        } catch (Exception ignored) {}

        cachedBattery = bat;
        lastBatteryFetchTime = now;
        return bat;
    }

    /**
     * Stops background processes and reports what was actually requested.
     *
     * Policy, persisted in {@link Prefs}:
     *  - "bloat" scope: only catalog entries of the "safe" tier.
     *  - "bloat+apps" scope (default): the above, plus every installed third-party app.
     *  - the user's Keep Alive list is always skipped, as are the catalog's
     *    protected tier, this app, Settings, SystemUI and "android".
     *
     * There is deliberately no hardcoded "important app" exception list any more.
     * WhatsApp, Telegram and friends keep a network connection and keep receiving
     * messages after being swiped out of Recents, which is exactly the drain the
     * user is trying to stop - so what may keep running is the user's decision.
     */
    @JavascriptInterface
    public String sweepBackgroundRamJson() {
        try {
            ActivityManager am = (ActivityManager) ctx.getSystemService(Context.ACTIVITY_SERVICE);
            if (am == null) {
                return "{\"ok\":false,\"message\":\"ActivityManager unavailable\"}";
            }

            ActivityManager.MemoryInfo before = new ActivityManager.MemoryInfo();
            am.getMemoryInfo(before);

            boolean includeAllApps = Prefs.sweepAllApps(ctx);
            Set<String> keepAlive = Prefs.keepAlive(ctx);
            PackageManager pm = ctx.getPackageManager();
            Set<String> targets = new LinkedHashSet<String>();

            // 1) Curated bloat: safe tier only, and only what is really installed.
            for (int i = 0; i < HuaweiCatalog.ENTRIES.length; i++) {
                HuaweiCatalog.BloatEntry entry = HuaweiCatalog.ENTRIES[i];
                if (!"safe".equals(entry.tier)) continue;
                if (keepAlive.contains(entry.pkg)) continue;
                if (HuaweiCatalog.isProtected(entry.pkg)) continue;
                if (!isInstalled(pm, entry.pkg)) continue;
                targets.add(entry.pkg);
            }

            // 2) Optionally every other third-party app.
            if (includeAllApps) {
                List<ApplicationInfo> apps = pm.getInstalledApplications(0);
                for (int i = 0; i < apps.size(); i++) {
                    ApplicationInfo ai = apps.get(i);
                    if (ai == null || ai.packageName == null) continue;
                    String p = ai.packageName;
                    if (p.equals(ctx.getPackageName())) continue;
                    if ((ai.flags & ApplicationInfo.FLAG_SYSTEM) != 0) continue;
                    if (HuaweiCatalog.isProtected(p)) continue;
                    if (keepAlive.contains(p)) continue;
                    targets.add(p);
                }
            }

            int requested = 0;
            for (String pkg : targets) {
                am.killBackgroundProcesses(pkg);
                requested++;
            }

            // Give AMS a moment to reap the processes before sampling free memory.
            // This runs on the WebView bridge thread (not the UI thread) and the
            // button shows a busy state while it happens.
            try {
                Thread.sleep(300L);
            } catch (InterruptedException ie) {
                Thread.currentThread().interrupt();
            }

            ActivityManager.MemoryInfo after = new ActivityManager.MemoryInfo();
            am.getMemoryInfo(after);

            // Report the real delta, which may legitimately be 0 or negative. The
            // previous version floored this at 16 MB, so the banner always claimed
            // memory had been freed even when none had.
            long deltaMb = (after.availMem - before.availMem) / 1048576L;

            JSONObject res = new JSONObject();
            res.put("ok", true);
            res.put("requestedCount", requested);
            res.put("freedMb", deltaMb);
            res.put("availMb", after.availMem / 1048576L);
            res.put("scope", includeAllApps ? "bloat+apps" : "bloat");
            return res.toString();
        } catch (Exception e) {
            return "{\"ok\":false,\"message\":\"" + safeJson(e.getMessage()) + "\"}";
        }
    }

    private boolean isInstalled(PackageManager pm, String pkg) {
        try {
            pm.getApplicationInfo(pkg, 0);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    /**
     * Everything the user can put on the Keep Alive list, plus the current sweep
     * scope. Curated (catalog) packages come first, then installed third-party apps
     * alphabetically by label.
     */
    @JavascriptInterface
    public String getKeepAliveJson() {
        try {
            PackageManager pm = ctx.getPackageManager();
            Set<String> keepAlive = Prefs.keepAlive(ctx);
            List<ApplicationInfo> apps = pm.getInstalledApplications(0);

            JSONArray curated = new JSONArray();
            Set<String> seen = new LinkedHashSet<String>();
            for (int i = 0; i < HuaweiCatalog.ENTRIES.length; i++) {
                HuaweiCatalog.BloatEntry e = HuaweiCatalog.ENTRIES[i];
                if ("protected".equals(e.tier)) continue;
                if (!isInstalled(pm, e.pkg)) continue;
                seen.add(e.pkg);
                curated.put(keepAliveItem(e.pkg, e.title, keepAlive.contains(e.pkg), true));
            }

            // {label, package} pairs; resolving each label exactly once instead of
            // once per Comparison during the sort.
            List<String[]> userApps = new ArrayList<String[]>();
            for (int i = 0; i < apps.size(); i++) {
                ApplicationInfo ai = apps.get(i);
                if (ai == null || ai.packageName == null) continue;
                if ((ai.flags & ApplicationInfo.FLAG_SYSTEM) != 0) continue;
                if (ai.packageName.equals(ctx.getPackageName())) continue;
                if (seen.contains(ai.packageName)) continue;
                userApps.add(new String[] { labelOf(ai), ai.packageName });
            }
            Collections.sort(userApps, new Comparator<String[]>() {
                @Override
                public int compare(String[] a, String[] b) {
                    return a[0].compareToIgnoreCase(b[0]);
                }
            });

            JSONArray others = new JSONArray();
            for (int i = 0; i < userApps.size(); i++) {
                String[] pair = userApps.get(i);
                others.put(keepAliveItem(pair[1], pair[0], keepAlive.contains(pair[1]), false));
            }

            JSONObject out = new JSONObject();
            out.put("sweepAllApps", Prefs.sweepAllApps(ctx));
            out.put("curated", curated);
            out.put("others", others);
            return out.toString();
        } catch (Exception e) {
            return "{\"sweepAllApps\":true,\"curated\":[],\"others\":[]}";
        }
    }

    private JSONObject keepAliveItem(String pkg, String label, boolean kept, boolean curated) throws Exception {
        JSONObject o = new JSONObject();
        o.put("pkg", pkg);
        o.put("label", label);
        o.put("kept", kept);
        o.put("curated", curated);
        return o;
    }

    private String labelOf(ApplicationInfo ai) {
        try {
            CharSequence cs = ctx.getPackageManager().getApplicationLabel(ai);
            if (cs != null && cs.length() > 0) return cs.toString();
        } catch (Exception ignored) {
        }
        return ai.packageName;
    }

    @JavascriptInterface
    public boolean setKeepAlive(String pkg, boolean kept) {
        try {
            Prefs.setKept(ctx, pkg, kept);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    @JavascriptInterface
    public boolean setSweepAllApps(boolean all) {
        try {
            Prefs.setSweepAllApps(ctx, all);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    @JavascriptInterface
    public String getHuaweiBloatListJson() {
        return buildBloatListJson();
    }

    private String buildBloatListJson() {
        try {
            boolean canReadStats = hasUsageAccess() && Build.VERSION.SDK_INT >= 26;
            long now = System.currentTimeMillis();

            // Per-package StorageStats queries are binder round-trips; this list is
            // re-read on every tab switch and every refresh, so memoise it briefly.
            if (cachedBloatJson != null
                    && cachedBloatStatsState == canReadStats
                    && now - lastBloatScanTime < SCAN_CACHE_MS) {
                return cachedBloatJson;
            }

            PackageManager pm = ctx.getPackageManager();
            StorageStatsManager ssm = null;
            if (canReadStats) {
                ssm = (StorageStatsManager) ctx.getSystemService(Context.STORAGE_STATS_SERVICE);
            }

            JSONArray arr = new JSONArray();
            for (int i = 0; i < HuaweiCatalog.ENTRIES.length; i++) {
                HuaweiCatalog.BloatEntry e = HuaweiCatalog.ENTRIES[i];
                JSONObject obj = new JSONObject();
                obj.put("pkg", e.pkg);
                obj.put("title", e.title);
                obj.put("category", e.category);
                obj.put("tier", e.tier);
                obj.put("impact", e.impact);
                obj.put("desc", e.desc);

                String state = "not_installed";
                double cacheMb = -1.0;
                try {
                    ApplicationInfo ai = pm.getApplicationInfo(e.pkg, 0);
                    state = ai.enabled ? "active" : "disabled";
                    if (canReadStats && ssm != null) {
                        StorageStats st = ssm.queryStatsForPackage(
                                StorageManager.UUID_DEFAULT,
                                e.pkg,
                                android.os.Process.myUserHandle()
                        );
                        cacheMb = round1(st.getCacheBytes() / 1048576.0);
                    }
                } catch (PackageManager.NameNotFoundException notFound) {
                    state = "not_installed";
                } catch (Exception ignored) {
                }

                obj.put("state", state);
                obj.put("cacheMb", cacheMb);
                arr.put(obj);
            }
            cachedBloatJson = arr.toString();
            cachedBloatStatsState = canReadStats;
            lastBloatScanTime = now;
            return cachedBloatJson;
        } catch (Exception e) {
            return "[]";
        }
    }

    private static class CacheItem {
        String pkg;
        String label;
        long cacheBytes;
        long totalBytes;
    }

    /**
     * Cache sizes per app.
     *
     * Runs on the scan executor (see scanCachesAsync), never on the WebView thread:
     * each queryStatsForPackage() is a binder round-trip, and the first version of
     * this method spent seconds blocking the single-threaded JS bridge. System
     * packages are skipped (they are most of the list and rarely what a user
     * reclaims) and results are memoised so revisiting a tab is free.
     */
    private String buildCacheScanJson() {
        try {
            if (!hasUsageAccess() || Build.VERSION.SDK_INT < 26) {
                cachedCacheJson = null;
                return "{\"needsUsageAccess\":true,\"items\":[]}";
            }
            long now = System.currentTimeMillis();
            if (cachedCacheJson != null && now - lastCacheScanTime < SCAN_CACHE_MS) {
                return cachedCacheJson;
            }

            PackageManager pm = ctx.getPackageManager();
            StorageStatsManager ssm = (StorageStatsManager) ctx.getSystemService(Context.STORAGE_STATS_SERVICE);
            if (ssm == null) {
                return "{\"needsUsageAccess\":false,\"error\":true,\"message\":\"Storage stats service unavailable\",\"items\":[]}";
            }

            List<ApplicationInfo> apps = pm.getInstalledApplications(0);
            List<CacheItem> items = new ArrayList<CacheItem>();
            long allCacheBytes = 0L;
            int scanned = 0;
            int failedQueries = 0;
            int processed = 0;

            int totalCandidates = 0;
            for (int i = 0; i < apps.size(); i++) {
                ApplicationInfo ai = apps.get(i);
                if (ai == null || ai.packageName == null) continue;
                if ((ai.flags & ApplicationInfo.FLAG_SYSTEM) != 0) continue;
                totalCandidates++;
            }

            for (int i = 0; i < apps.size(); i++) {
                ApplicationInfo ai = apps.get(i);
                if (ai == null || ai.packageName == null) continue;
                if ((ai.flags & ApplicationInfo.FLAG_SYSTEM) != 0) continue;
                try {
                    StorageStats st = ssm.queryStatsForPackage(
                            StorageManager.UUID_DEFAULT,
                            ai.packageName,
                            android.os.Process.myUserHandle()
                    );
                    scanned++;
                    long cb = st.getCacheBytes();
                    // Total counts every scanned app, so the headline figure is not
                    // silently limited to the apps large enough to list below.
                    allCacheBytes += cb;
                    if (cb >= 2L * 1048576L) { // >= 2 MB cache
                        CacheItem ci = new CacheItem();
                        ci.pkg = ai.packageName;
                        ci.label = labelOf(ai);
                        ci.cacheBytes = cb;
                        ci.totalBytes = st.getAppBytes() + st.getDataBytes();
                        items.add(ci);
                    }
                } catch (Exception ignored) {
                    failedQueries++;
                }
                processed++;
                if (processed % 8 == 0 || processed == totalCandidates) {
                    postJs("window.onScanProgress && window.onScanProgress('cache',"
                            + processed + "," + totalCandidates + ")");
                }
            }

            if (scanned == 0 && totalCandidates > 0) {
                return "{\"needsUsageAccess\":false,\"error\":true,\"message\":\"Could not read cache sizes. Check Usage Access and retry.\",\"items\":[]}";
            }

            Collections.sort(items, new Comparator<CacheItem>() {
                @Override
                public int compare(CacheItem a, CacheItem b) {
                    return Long.compare(b.cacheBytes, a.cacheBytes);
                }
            });

            JSONArray arr = new JSONArray();
            int limit = Math.min(30, items.size());
            for (int i = 0; i < limit; i++) {
                CacheItem ci = items.get(i);
                JSONObject o = new JSONObject();
                o.put("pkg", ci.pkg);
                o.put("label", ci.label);
                o.put("cacheMb", round1(ci.cacheBytes / 1048576.0));
                o.put("totalMb", round1(ci.totalBytes / 1048576.0));
                arr.put(o);
            }

            JSONObject out = new JSONObject();
            out.put("needsUsageAccess", false);
            out.put("totalCacheMb", round1(allCacheBytes / 1048576.0));
            out.put("scannedApps", scanned);
            out.put("failedApps", failedQueries);
            out.put("items", arr);
            cachedCacheJson = out.toString();
            lastCacheScanTime = now;
            return cachedCacheJson;
        } catch (Exception e) {
            return "{\"needsUsageAccess\":false,\"error\":true,\"message\":\""
                    + safeJson(e.getMessage()) + "\",\"items\":[]}";
        }
    }

    /** Drops memoised scan results so the next read reflects the current state. */
    @JavascriptInterface
    public void invalidateScanCaches() {
        lastCacheScanTime = 0L;
        lastBloatScanTime = 0L;
        cachedCacheJson = null;
        cachedBloatJson = null;
    }

    /** Runs a JS snippet on the WebView thread. Safe to call from the scan thread. */
    private void postJs(final String js) {
        mainHandler.post(new Runnable() {
            @Override
            public void run() {
                if (webView == null) return;
                try {
                    webView.evaluateJavascript(js, null);
                } catch (Exception ignored) {
                }
            }
        });
    }

    /**
     * Scans caches off the JS thread and streams progress plus the result back to the
     * page. The synchronous variant blocks the single-threaded WebView for seconds on
     * a P20 Lite (~150 binder round-trips), which is what made this tab feel frozen.
     */
    @JavascriptInterface
    public void scanCachesAsync() {
        scanExecutor.execute(new Runnable() {
            @Override
            public void run() {
                String json;
                try {
                    json = buildCacheScanJson();
                } catch (Exception e) {
                    json = "{\"needsUsageAccess\":false,\"error\":true,\"items\":[]}";
                }
                postJs("window.onCacheScan && window.onCacheScan(" + json + ")");
            }
        });
    }

    /** Async variant of the bloat catalog read (29 StorageStats queries). */
    @JavascriptInterface
    public void scanBloatListAsync() {
        scanExecutor.execute(new Runnable() {
            @Override
            public void run() {
                String json;
                try {
                    json = buildBloatListJson();
                } catch (Exception e) {
                    json = "[]";
                }
                postJs("window.onBloatScan && window.onBloatScan(" + json + ")");
            }
        });
    }

    /** Called from MainActivity.onDestroy(). */
    public void shutdown() {
        try {
            scanExecutor.shutdownNow();
        } catch (Exception ignored) {
        }
    }

    @JavascriptInterface
    public String startAutomation(String mode, String csvPackages) {
        if (!AutomationEngine.MODE_FORCE_STOP.equals(mode)
                && !AutomationEngine.MODE_DISABLE.equals(mode)
                && !AutomationEngine.MODE_CLEAR_CACHE.equals(mode)) {
            return "{\"ok\":false,\"message\":\"Unsupported automation mode.\"}";
        }
        if (!isSupportedDevice()) {
            return "{\"ok\":false,\"unsupportedDevice\":true,\"message\":\"Automation is limited to Huawei ANE-LX1 running Android 9 / EMUI 9.1.\"}";
        }
        if (!hasAccessibilityEnabled()) {
            boolean listed = isAccessibilityListedInSettings();
            if (listed) {
                // The switch looks on but the service is not bound - EMUI's battery
                // manager kills it routinely. Starting a run here would drive Settings
                // with nothing clicking, and the user could not reach the in-app cancel.
                showToast("The Accessibility service is switched on but not running (EMUI stops it). "
                        + "Toggle it OFF and ON in Settings, then tap again.");
            } else {
                openPermissionScreen("accessibility");
                showToast("Turn ON 'AnneControl Auto-Cleaner' in Accessibility first, then tap again!");
            }
            return "{\"ok\":false,\"needsAccessibility\":true,\"serviceListed\":" + listed + "}";
        }
        if (csvPackages == null || csvPackages.trim().isEmpty()) {
            return "{\"ok\":false,\"message\":\"No apps selected.\"}";
        }
        String[] parts = csvPackages.split(",");
        List<String> list = new ArrayList<String>();
        for (int i = 0; i < parts.length; i++) {
            String p = parts[i].trim();
            if (p.length() > 0 && !list.contains(p)) list.add(p);
        }

        AutomationEngine engine = AutomationEngine.get();
        engine.start(ctx, mode, list);
        int queued = engine.getTotalCount();
        if (!engine.isRunning()) {
            return "{\"ok\":false,\"queued\":" + queued + ",\"running\":false,\"message\":\""
                    + safeJson(engine.getStatusMessage()) + "\"}";
        }
        return "{\"ok\":true,\"queued\":" + queued + ",\"running\":true}";
    }

    @JavascriptInterface
    public void stopAutomation() {
        AutomationEngine.get().stop();
    }

    @JavascriptInterface
    public String getAutomationStatusJson() {
        try {
            AutomationEngine eng = AutomationEngine.get();
            JSONObject o = new JSONObject();
            o.put("running", eng.isRunning());
            o.put("mode", eng.getMode());
            o.put("currentIndex", eng.getCurrentIndex());
            o.put("totalCount", eng.getTotalCount());
            o.put("succeededCount", eng.getSuccessCount());
            o.put("skippedCount", eng.getSkippedCount());
            o.put("failedCount", eng.getFailedCount());
            o.put("currentPackage", eng.getCurrentPackage());
            o.put("expectedLabel", eng.getExpectedLabel());
            o.put("message", eng.getStatusMessage());
            return o.toString();
        } catch (Exception e) {
            return "{\"running\":false}";
        }
    }

    /**
     * One-shot summary of the last finished run (completion, abort or cancel).
     * Consuming it here is what stops the banner re-appearing on every resume.
     */
    @JavascriptInterface
    public String consumeRunSummaryJson() {
        try {
            JSONObject o = new JSONObject();
            String summary = AutomationEngine.get().consumeSummary();
            o.put("available", summary != null);
            o.put("message", summary != null ? summary : "");
            o.put("running", AutomationEngine.get().isRunning());
            return o.toString();
        } catch (Exception e) {
            return "{\"available\":false,\"message\":\"\"}";
        }
    }

    @JavascriptInterface
    public boolean setCompactFontScale(String scaleStr) {
        if (!hasWriteSettings()) {
            openPermissionScreen("write_settings");
            showToast("Flip ON 'Allow modifying system settings' for AnneControl, then tap again!");
            return false;
        }
        try {
            float scale = Float.parseFloat(scaleStr);
            if (Float.isNaN(scale) || Float.isInfinite(scale)) {
                return false;
            }
            if (scale < 0.80f) scale = 0.80f;
            if (scale > 1.25f) scale = 1.25f;
            float current = Settings.System.getFloat(
                    ctx.getContentResolver(), Settings.System.FONT_SCALE, 1.0f);
            Prefs.rememberOriginalFontScale(ctx, current);
            boolean written = Settings.System.putFloat(
                    ctx.getContentResolver(), Settings.System.FONT_SCALE, scale);
            if (!written) {
                showToast("Android rejected the text-scale change.");
                return false;
            }
            showToast("Applied " + scale + "x UI text scale! Some screens update on the next "
                    + "unlock or reboot.");
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    @JavascriptInterface
    public boolean restoreOriginalFontScale() {
        if (!hasWriteSettings()) {
            openPermissionScreen("write_settings");
            showToast("Allow AnneControl to modify system settings, then try again.");
            return false;
        }
        if (!Prefs.hasOriginalFontScale(ctx)) {
            showToast("No previous text scale was saved by AnneControl.");
            return false;
        }
        try {
            float original = Prefs.originalFontScale(ctx, 1.0f);
            boolean written = Settings.System.putFloat(
                    ctx.getContentResolver(), Settings.System.FONT_SCALE, original);
            if (!written) {
                showToast("Android rejected the text-scale restore.");
                return false;
            }
            Prefs.clearOriginalFontScale(ctx);
            showToast("Restored your previous system text scale to " + original + "x.");
            return true;
        } catch (Exception e) {
            showToast("Could not restore text scale.");
            return false;
        }
    }

    /** Starts a local file selection and structural preview for a Huawei .hwt theme. */
    @JavascriptInterface
    public void importHuaweiTheme() {
        if (activity instanceof MainActivity) {
            ((MainActivity) activity).beginHuaweiThemeImport();
        } else {
            showToast("Theme preview is unavailable from this screen.");
        }
    }

    /** Starts the folder picker only after the user reviewed the package preview. */
    @JavascriptInterface
    public void beginThemeFolderSelection() {
        if (activity instanceof MainActivity) {
            ((MainActivity) activity).beginThemeFolderSelection();
        } else {
            showToast("Theme import is unavailable from this screen.");
        }
    }

    @JavascriptInterface
    public void openAppInfo(String pkg) {
        try {
            Intent i = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
            i.setData(Uri.parse("package:" + pkg));
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            ctx.startActivity(i);
        } catch (Exception e) {
            showToast("App not installed on this firmware.");
        }
    }

    @JavascriptInterface
    public void copyToClipboard(String text, String toastMsg) {
        try {
            ClipboardManager cm = (ClipboardManager) ctx.getSystemService(Context.CLIPBOARD_SERVICE);
            if (cm != null) {
                ClipData clip = ClipData.newPlainText("AnneControl", text);
                cm.setPrimaryClip(clip);
                showToast(toastMsg != null ? toastMsg : "Copied to clipboard!");
            }
        } catch (Exception e) {
            showToast("Failed to copy: " + e.getMessage());
        }
    }

    @JavascriptInterface
    public void shareText(String title, String content) {
        try {
            Intent share = new Intent(Intent.ACTION_SEND);
            share.setType("text/plain");
            share.putExtra(Intent.EXTRA_SUBJECT, title);
            share.putExtra(Intent.EXTRA_TEXT, content);
            Intent chooser = Intent.createChooser(share, title);
            chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            ctx.startActivity(chooser);
        } catch (Exception e) {
            showToast("Sharing failed: " + e.getMessage());
        }
    }

    @JavascriptInterface
    public void openDialerCode(String code) {
        try {
            Intent intent = new Intent(Intent.ACTION_DIAL);
            intent.setData(Uri.parse("tel:" + Uri.encode(code)));
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            ctx.startActivity(intent);
        } catch (Exception e) {
            showToast("Could not open dialer: " + e.getMessage());
        }
    }

    @JavascriptInterface
    public void openPermissionScreen(String target) {
        try {
            Intent intent = null;
            if ("usage".equals(target)) {
                intent = new Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS);
                showToast("Tap 'AnneControl' and switch ON Permit usage access!");
            } else if ("accessibility".equals(target)) {
                intent = new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS);
                showToast("Under Downloaded services, turn ON 'AnneControl Auto-Cleaner'!");
            } else if ("write_settings".equals(target)) {
                intent = new Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS);
                intent.setData(Uri.parse("package:" + ctx.getPackageName()));
            } else if ("battery_exempt".equals(target)) {
                intent = new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS);
                intent.setData(Uri.parse("package:" + ctx.getPackageName()));
            } else if ("raw_doze".equals(target)) {
                intent = new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS);
                showToast("Set WhatsApp / Gmail to 'Don't allow' battery optimization so messages arrive instantly!");
            } else if ("huawei_applaunch".equals(target)) {
                openHuaweiHiddenPowerManager();
                return;
            } else if ("dev_options".equals(target)) {
                openDeveloperAnimationsMenu();
                return;
            } else if ("storage_manager".equals(target)) {
                intent = new Intent(Settings.ACTION_INTERNAL_STORAGE_SETTINGS);
            } else if ("application_settings".equals(target)) {
                intent = new Intent(Settings.ACTION_APPLICATION_SETTINGS);
            }

            if (intent != null) {
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                ctx.startActivity(intent);
            }
        } catch (Exception e) {
            showToast("Could not open menu: " + e.getMessage());
        }
    }

    private void openHuaweiHiddenPowerManager() {
        String[][] candidates = new String[][] {
            { "com.huawei.systemmanager", "com.huawei.systemmanager.startupmgr.ui.StartupNormalAppListActivity" },
            { "com.huawei.systemmanager", "com.huawei.systemmanager.optimize.process.ProtectActivity" },
            { "com.huawei.systemmanager", "com.huawei.systemmanager.power.ui.HwPowerManagerActivity" }
        };
        for (int i = 0; i < candidates.length; i++) {
            try {
                Intent intent = new Intent();
                intent.setComponent(new ComponentName(candidates[i][0], candidates[i][1]));
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                ctx.startActivity(intent);
                showToast("Turn OFF 'Manage automatically' for WhatsApp & key apps!");
                return;
            } catch (Exception ignored) {
            }
        }
        try {
            Intent fallback = ctx.getPackageManager().getLaunchIntentForPackage("com.huawei.systemmanager");
            if (fallback != null) {
                fallback.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                ctx.startActivity(fallback);
                return;
            }
        } catch (Exception ignored) {
        }
        openPermissionScreen("raw_doze");
    }

    private void openDeveloperAnimationsMenu() {
        try {
            int devEnabled = Settings.Global.getInt(
                    ctx.getContentResolver(),
                    Settings.Global.DEVELOPMENT_SETTINGS_ENABLED,
                    0
            );
            if (devEnabled == 0) {
                Intent about = new Intent(Settings.ACTION_DEVICE_INFO_SETTINGS);
                about.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                ctx.startActivity(about);
                showToast("Tap 'Build number' 7 times first to unlock Developer Options!");
                return;
            }
            Intent dev = new Intent(Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS);
            dev.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            ctx.startActivity(dev);
            showToast("Scroll to Window / Transition / Animator scale and set all 3 to 0.5x!");
        } catch (Exception e) {
            Intent about = new Intent(Settings.ACTION_DEVICE_INFO_SETTINGS);
            about.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            ctx.startActivity(about);
        }
    }

    private void showToast(final String msg) {
        mainHandler.post(new Runnable() {
            @Override
            public void run() {
                Toast.makeText(ctx, msg, Toast.LENGTH_LONG).show();
            }
        });
    }

    private long parseKbLineToMb(String line) {
        try {
            String[] parts = line.trim().split("\\s+");
            if (parts.length >= 2) {
                return Long.parseLong(parts[1]) / 1024L;
            }
        } catch (Exception ignored) {
        }
        return 0L;
    }

    private double round1(double v) {
        return Math.round(v * 10.0) / 10.0;
    }

    private double round2(double v) {
        return Math.round(v * 100.0) / 100.0;
    }

    private String safeJson(String s) {
        if (s == null) return "error";
        return s.replace("\\", "\\\\").replace("\"", "'").replace("\n", " ");
    }
}
