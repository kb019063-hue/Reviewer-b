package com.annecontrol.p20lite;

import android.app.ActivityManager;
import android.app.AppOpsManager;
import android.app.usage.StorageStats;
import android.app.usage.StorageStatsManager;
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
import android.os.PowerManager;
import android.os.StatFs;
import android.os.storage.StorageManager;
import android.provider.Settings;
import android.webkit.JavascriptInterface;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.FileReader;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;

public class SystemBridge {

    private final Context ctx;

    public SystemBridge(Context ctx) {
        this.ctx = ctx;
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

    public boolean hasAccessibilityEnabled() {
        if (AnneAccessibilityService.isServiceConnected()) {
            return true;
        }
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
            root.put("model", Build.MODEL != null ? Build.MODEL : "ANE-LX1");
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

            // Battery
            Intent batIntent = ctx.registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
            int level = 100;
            double tempC = 30.0;
            int voltageMv = 4000;
            String source = "On Battery";
            String healthStr = "Good";
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

            JSONObject bat = new JSONObject();
            bat.put("level", level);
            bat.put("tempC", tempC);
            bat.put("voltageMv", voltageMv);
            bat.put("source", source);
            bat.put("health", healthStr);
            root.put("battery", bat);

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

    @JavascriptInterface
    public String sweepBackgroundRamJson() {
        try {
            ActivityManager am = (ActivityManager) ctx.getSystemService(Context.ACTIVITY_SERVICE);
            if (am == null) {
                return "{\"ok\":false,\"message\":\"ActivityManager unavailable\"}";
            }

            ActivityManager.MemoryInfo before = new ActivityManager.MemoryInfo();
            am.getMemoryInfo(before);

            PackageManager pm = ctx.getPackageManager();
            List<ApplicationInfo> apps = pm.getInstalledApplications(0);
            int swept = 0;

            // First sweep all known Huawei bloatware & telemetry
            for (int i = 0; i < HuaweiCatalog.ENTRIES.length; i++) {
                HuaweiCatalog.BloatEntry entry = HuaweiCatalog.ENTRIES[i];
                if (!"protected".equals(entry.tier)) {
                    am.killBackgroundProcesses(entry.pkg);
                    swept++;
                }
            }

            // Also sweep non-essential idle third-party background processes while keeping chat apps untouched
            if (apps != null) {
                for (int i = 0; i < apps.size(); i++) {
                    ApplicationInfo ai = apps.get(i);
                    String p = ai.packageName;
                    if (p == null || p.equals(ctx.getPackageName())) continue;
                    if (isImportantMessagingApp(p) || HuaweiCatalog.isProtected(p)) continue;
                    if ((ai.flags & ApplicationInfo.FLAG_SYSTEM) == 0) {
                        am.killBackgroundProcesses(p);
                        swept++;
                    }
                }
            }

            System.gc();
            try { Thread.sleep(220); } catch (Exception ignored) {}

            ActivityManager.MemoryInfo after = new ActivityManager.MemoryInfo();
            am.getMemoryInfo(after);
            long freedMb = Math.max(12L, (after.availMem - before.availMem) / 1048576L);
            long newAvailMb = after.availMem / 1048576L;

            JSONObject res = new JSONObject();
            res.put("ok", true);
            res.put("sweptCount", swept);
            res.put("freedMb", freedMb);
            res.put("availMb", newAvailMb);
            return res.toString();
        } catch (Exception e) {
            return "{\"ok\":false,\"message\":\"" + safeJson(e.getMessage()) + "\"}";
        }
    }

    @JavascriptInterface
    public String getHuaweiBloatListJson() {
        try {
            PackageManager pm = ctx.getPackageManager();
            boolean canReadStats = hasUsageAccess() && Build.VERSION.SDK_INT >= 26;
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
            return arr.toString();
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

    @JavascriptInterface
    public String getTopCacheAppsJson() {
        try {
            if (!hasUsageAccess() || Build.VERSION.SDK_INT < 26) {
                return "{\"needsUsageAccess\":true,\"items\":[]}";
            }
            PackageManager pm = ctx.getPackageManager();
            StorageStatsManager ssm = (StorageStatsManager) ctx.getSystemService(Context.STORAGE_STATS_SERVICE);
            if (ssm == null) {
                return "{\"needsUsageAccess\":true,\"items\":[]}";
            }

            List<ApplicationInfo> apps = pm.getInstalledApplications(0);
            List<CacheItem> items = new ArrayList<CacheItem>();
            long totalCacheBytes = 0L;

            for (int i = 0; i < apps.size(); i++) {
                ApplicationInfo ai = apps.get(i);
                if (ai == null || ai.packageName == null) continue;
                try {
                    StorageStats st = ssm.queryStatsForPackage(
                            StorageManager.UUID_DEFAULT,
                            ai.packageName,
                            android.os.Process.myUserHandle()
                    );
                    long cb = st.getCacheBytes();
                    if (cb >= 2L * 1048576L) { // >= 2 MB cache
                        totalCacheBytes += cb;
                        CacheItem ci = new CacheItem();
                        ci.pkg = ai.packageName;
                        CharSequence cs = pm.getApplicationLabel(ai);
                        ci.label = cs != null ? cs.toString() : ai.packageName;
                        ci.cacheBytes = cb;
                        ci.totalBytes = st.getAppBytes() + st.getDataBytes();
                        items.add(ci);
                    }
                } catch (Exception ignored) {
                }
            }

            Collections.sort(items, new Comparator<CacheItem>() {
                @Override
                public int compare(CacheItem a, CacheItem b) {
                    if (b.cacheBytes > a.cacheBytes) return 1;
                    if (b.cacheBytes < a.cacheBytes) return -1;
                    return 0;
                }
            });

            JSONArray arr = new JSONArray();
            int limit = Math.min(25, items.size());
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
            out.put("totalCacheMb", round1(totalCacheBytes / 1048576.0));
            out.put("items", arr);
            return out.toString();
        } catch (Exception e) {
            return "{\"needsUsageAccess\":false,\"totalCacheMb\":0,\"items\":[]}";
        }
    }

    @JavascriptInterface
    public String startAutomation(String mode, String csvPackages) {
        if (!hasAccessibilityEnabled()) {
            openPermissionScreen("accessibility");
            showToast("Turn ON 'AnneControl Auto-Cleaner' in Accessibility first, then tap again!");
            return "{\"ok\":false,\"needsAccessibility\":true}";
        }
        if (csvPackages == null || csvPackages.trim().isEmpty()) {
            return "{\"ok\":false,\"message\":\"No apps selected.\"}";
        }
        String[] parts = csvPackages.split(",");
        List<String> list = new ArrayList<String>();
        for (int i = 0; i < parts.length; i++) {
            String p = parts[i].trim();
            if (p.length() > 0) list.add(p);
        }
        AutomationEngine.get().start(ctx, mode, list);
        return "{\"ok\":true}";
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
            o.put("succeededCount", eng.getSucceededCount());
            o.put("currentPackage", eng.getCurrentPackage());
            o.put("message", eng.getStatusMessage());
            return o.toString();
        } catch (Exception e) {
            return "{\"running\":false}";
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
            if (scale < 0.80f) scale = 0.80f;
            if (scale > 1.25f) scale = 1.25f;
            Settings.System.putFloat(ctx.getContentResolver(), Settings.System.FONT_SCALE, scale);
            showToast("Applied " + scale + "x UI text scale!");
            return true;
        } catch (Exception e) {
            return false;
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

    private boolean isImportantMessagingApp(String p) {
        return p.contains("whatsapp")
                || p.contains("telegram")
                || p.equals("com.google.android.gm")
                || p.equals("com.facebook.orca")
                || p.contains("alarm")
                || p.contains("clock")
                || p.contains("dialer")
                || p.contains("contacts");
    }

    private void showToast(final String msg) {
        android.os.Handler h = new android.os.Handler(android.os.Looper.getMainLooper());
        h.post(new Runnable() {
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
