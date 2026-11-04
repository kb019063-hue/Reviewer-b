package com.annecontrol.p20lite;

import android.content.Context;
import android.content.SharedPreferences;

import java.util.HashSet;
import java.util.Set;

/**
 * Small persisted-preference helper.
 *
 * Holds the two user decisions that decide how aggressive the RAM sweep is:
 *
 *  - {@code keepAlive}: packages that must never be killed. It is deliberately
 *    EMPTY by default. The previous version hard-coded nine "important" apps
 *    (WhatsApp, Telegram, ...) as unkillable, which meant a user who wanted
 *    WhatsApp's background drain stopped could not do it from the app at all.
 *  - {@code sweepAllApps}: whether the sweep also walks installed third-party
 *    apps, or sticks to the curated AnneControl bloat catalog.
 *
 * SharedPreferences.getStringSet() returns a live, shared set, so every write
 * copies it first (mutating the returned set in place is undefined behaviour
 * and leaks between reads).
 */
final class Prefs {

    private static final String FILE = "annecontrol";
    private static final String KEY_KEEP_ALIVE = "keep_alive";
    private static final String KEY_SWEEP_ALL = "sweep_all_apps";

    private Prefs() {
    }

    private static SharedPreferences prefs(Context ctx) {
        return ctx.getApplicationContext().getSharedPreferences(FILE, Context.MODE_PRIVATE);
    }

    static Set<String> keepAlive(Context ctx) {
        Set<String> stored;
        try {
            stored = prefs(ctx).getStringSet(KEY_KEEP_ALIVE, null);
        } catch (Exception e) {
            stored = null;
        }
        Set<String> copy = new HashSet<String>();
        if (stored != null) {
            copy.addAll(stored);
        }
        return copy;
    }

    static void setKept(Context ctx, String pkg, boolean kept) {
        if (pkg == null || pkg.length() == 0) return;
        Set<String> copy = keepAlive(ctx);
        if (kept) {
            copy.add(pkg);
        } else {
            copy.remove(pkg);
        }
        prefs(ctx).edit().putStringSet(KEY_KEEP_ALIVE, copy).apply();
    }

    /** Defaults to true: the sweep is advertised as "sweep background bloat and apps". */
    static boolean sweepAllApps(Context ctx) {
        return prefs(ctx).getBoolean(KEY_SWEEP_ALL, true);
    }

    static void setSweepAllApps(Context ctx, boolean all) {
        prefs(ctx).edit().putBoolean(KEY_SWEEP_ALL, all).apply();
    }
}
