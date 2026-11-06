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
        new BloatEntry("com.huawei.powergenie", "Huawei PowerGenie", "Power Management", "safe", "High",
            "Huawei power-management component. Its behavior varies by firmware; disabling it may change battery policy and may not prevent apps from reloading. Review before changing."),
        new BloatEntry("com.huawei.search", "Huawei HiSearch", "EMUI Home Clutter", "safe", "High",
            "Huawei home-screen search integration. Disabling removes its search feature; performance and memory effects vary by firmware."),
        new BloatEntry("com.huawei.intelligent", "Huawei Assistant / HiBoard", "EMUI Home Clutter", "safe", "High",
            "Huawei home-screen assistant/feed. Disabling removes this feature; background activity and memory impact vary by firmware."),
        new BloatEntry("com.huawei.Magazine", "Magazine Unlock", "EMUI Home Clutter", "safe", "Medium",
            "Provides rotating lock-screen wallpapers. It may download wallpaper assets; storage/network impact varies with settings."),
        new BloatEntry("com.huawei.hiview", "Huawei HiView Telemetry", "Background Logger", "safe", "High",
            "Huawei diagnostic component. Disabling may affect diagnostic logs or support functions; a storage or speed benefit is not guaranteed."),
        new BloatEntry("com.huawei.hiviewtunnel", "Huawei HiView Tunnel", "Background Logger", "safe", "Medium",
            "Background telemetry uploader companion for HiView."),
        new BloatEntry("com.huawei.bd", "Huawei User Analytics (HwUE)", "Background Logger", "safe", "Medium",
            "Huawei analytics component. Disabling may affect diagnostics or experience features; review the package on this firmware first."),
        new BloatEntry("com.huawei.himovie.overseas", "Huawei Video", "Media Bloat", "safe", "Medium",
            "Promotional streaming video player. Gallery still plays all camera videos normally."),
        new BloatEntry("com.android.mediacenter", "Huawei Music", "Media Bloat", "safe", "Medium",
            "Huawei music player. Disabling removes this player and may affect Huawei media integrations; it does not necessarily improve performance."),
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
            "Huawei's secondary app store. Disabling removes AppGallery access and may affect Huawei app updates; keep it if you rely on Huawei services."),
        new BloatEntry("com.huawei.hicloud", "Huawei Cloud", "Optional", "optional", "Medium",
            "Huawei cloud/synchronization service. Disabling can stop Huawei backups or sync; check which backup services you use first."),
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
