package com.annecontrol.p20lite;

public class HuaweiCatalog {

    public static class BloatEntry {
        public final String pkg;
        public final String title;
        public final String category;
        public final String tier; // "safe", "optional", "protected"
        public final String impact;
        public final String desc;

        public BloatEntry(String pkg, String title, String category, String tier, String impact, String desc) {
            this.pkg = pkg;
            this.title = title;
            this.category = category;
            this.tier = tier;
            this.impact = impact;
            this.desc = desc;
        }
    }

    public static final BloatEntry[] ENTRIES = new BloatEntry[] {
        new BloatEntry("com.huawei.powergenie", "Huawei PowerGenie Daemon", "Aggressive RAM Killer", "safe", "High",
            "Root cause of EMUI 9.1 app reloads! Kills recent background apps in under a minute regardless of free RAM. Disabling or stopping this allows apps to stay alive in Recent Apps."),
        new BloatEntry("com.huawei.search", "Huawei HiSearch", "EMUI Home Clutter", "safe", "High",
            "Laggy swipe-down global search bar on the home screen. Disabling or force-stopping frees RAM and stops accidental swipe lag."),
        new BloatEntry("com.huawei.intelligent", "Huawei Assistant / HiBoard", "EMUI Home Clutter", "safe", "High",
            "Leftmost home-screen news feed that stays resident in your 4 GB RAM and refreshes constantly."),
        new BloatEntry("com.huawei.Magazine", "Magazine Unlock", "EMUI Home Clutter", "safe", "Medium",
            "Downloads rotating lock-screen wallpapers in the background, eating storage and data."),
        new BloatEntry("com.huawei.hiview", "Huawei HiView Telemetry", "Background Logger", "safe", "High",
            "Writes diagnostic logs continuously in the background, slowing down eMMC 5.1 storage."),
        new BloatEntry("com.huawei.hiviewtunnel", "Huawei HiView Tunnel", "Background Logger", "safe", "Medium",
            "Background telemetry uploader companion for HiView."),
        new BloatEntry("com.huawei.bd", "Huawei User Analytics (HwUE)", "Background Logger", "safe", "Medium",
            "Tracks usage metrics in the background. Safe to stop/disable."),
        new BloatEntry("com.huawei.himovie.overseas", "Huawei Video", "Media Bloat", "safe", "Medium",
            "Promotional streaming video player. Gallery still plays all camera videos normally."),
        new BloatEntry("com.android.mediacenter", "Huawei Music", "Media Bloat", "safe", "Medium",
            "Built-in music app running background media scanners (safe if you use Spotify/VLC/YouTube)."),
        new BloatEntry("com.huawei.vassistant", "HiVoice Assistant", "Huawei Assistants", "safe", "High",
            "Huawei proprietary voice service. Google Assistant works independently without it."),
        new BloatEntry("com.huawei.hitouch", "Huawei HiTouch Shopping", "Huawei Assistants", "safe", "Medium",
            "Two-finger press shopping lookup overlay that monitors screen touches."),
        new BloatEntry("com.huawei.tips", "Huawei Tips", "Promotions", "safe", "Low",
            "Periodic 'Discover EMUI' popup notification service."),
        new BloatEntry("com.huawei.hifolder", "Huawei AppAdvisor", "Promotions", "safe", "Low",
            "Shows sponsored app suggestions inside home-screen folders."),
        new BloatEntry("com.huawei.phoneservice", "My Huawei / HiCare", "Promotions", "safe", "Medium",
            "Huawei support & promotional portal running background checks."),
        new BloatEntry("com.huawei.gameassistant", "Huawei Game Suite", "Utilities", "safe", "Medium",
            "Game overlay daemon that often adds extra stutter on the Kirin 659."),
        new BloatEntry("com.huawei.skytone", "Huawei SkyTone Roaming", "Utilities", "safe", "Low",
            "Virtual travel eSIM service; normal SIM cards and roaming do not use it."),
        new BloatEntry("com.booking", "Booking.com Preload", "Partner Bloat", "safe", "Low",
            "Factory partner app bundled on EMEA ANE-LX1 firmware."),
        new BloatEntry("com.facebook.appmanager", "Meta App Manager Daemon", "Partner Bloat", "safe", "Medium",
            "Hidden factory background updater. Play Store updates WhatsApp/Facebook normally without it."),
        new BloatEntry("com.facebook.services", "Meta Background Services", "Partner Bloat", "safe", "Medium",
            "Preloaded background Meta service on ANE-LX1 firmware."),
        new BloatEntry("com.facebook.system", "Meta Installer Stub", "Partner Bloat", "safe", "Low",
            "Silent background installer stub bundled at the factory."),
        new BloatEntry("com.netflix.partner.activation", "Netflix Partner Stub", "Partner Bloat", "safe", "Low",
            "Boot-time partner activation stub."),
        new BloatEntry("com.huawei.appmarket", "Huawei AppGallery", "Optional", "optional", "High",
            "Huawei's secondary app store. Safe to stop/disable if you use Google Play Store."),
        new BloatEntry("com.huawei.hicloud", "Huawei Cloud", "Optional", "optional", "Medium",
            "Huawei 5 GB sync service that triggers 'Storage Full' nags (safe if using Google Backup)."),
        new BloatEntry("com.huawei.health", "Huawei Health", "Optional", "optional", "High",
            "Runs a 24/7 step-counter daemon in RAM (keep only if you pair a Huawei Watch/Band)."),
        new BloatEntry("com.huawei.wallet", "Huawei Wallet", "Optional", "optional", "Low",
            "Huawei's payment app (separate from Google Wallet)."),
        new BloatEntry("com.huawei.android.launcher", "EMUI Home & Recent Apps", "Protected Core", "protected", "High",
            "Protected! Huawei tied the Recent Apps button into this package on EMUI 9.1. Install Lawnchair/Nova and set as Default Home instead of disabling this."),
        new BloatEntry("com.huawei.systemmanager", "Huawei System Manager", "Protected Core", "protected", "Medium",
            "Protected! Handles core permissions and battery settings on EMUI 9.1."),
        new BloatEntry("com.google.android.gms", "Google Play Services", "Protected Core", "protected", "High",
            "Protected! Required for Play Store, WhatsApp notifications, and Google apps.")
    };

    public static boolean isProtected(String pkg) {
        if (pkg == null) return true;
        if ("com.annecontrol.p20lite".equals(pkg)
                || "com.android.settings".equals(pkg)
                || "com.android.systemui".equals(pkg)
                || "android".equals(pkg)) {
            return true;
        }
        for (int i = 0; i < ENTRIES.length; i++) {
            if (ENTRIES[i].pkg.equals(pkg) && "protected".equals(ENTRIES[i].tier)) {
                return true;
            }
        }
        return false;
    }
}
