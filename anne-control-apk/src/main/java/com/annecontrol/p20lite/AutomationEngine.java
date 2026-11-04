package com.annecontrol.p20lite;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.graphics.drawable.Icon;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.provider.Settings;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Drives the Settings UI one package at a time: open App info, wait for
 * {@link AnneAccessibilityService} to report what it did, move on.
 *
 * Queue/outcome bookkeeping lives in {@link QueuePlanner} (pure Java, unit tested);
 * this class adds the Android bits: navigation, timeouts and the ongoing
 * notification that lets the user cancel while Settings is on top.
 *
 * Design notes (docs/CODE_REVIEW.md 1.1 / 2.6 / 3.2):
 *  - Every state transition funnels through {@link #advanceInternal(int, String)}, so
 *    counters, the safety timeout and the "open the next package" navigation cannot
 *    drift apart.
 *  - {@link #generation} invalidates callbacks queued by a previous run. Starting a
 *    new run while one was active used to leave a stale "open next package" runnable
 *    behind, which then skipped a package.
 *  - An ongoing notification with a STOP action (plus a Volume Down hook in the
 *    accessibility service) is the only way to cancel while Settings is in front.
 */
public class AutomationEngine {

    public static final String MODE_NONE = "none";
    public static final String MODE_FORCE_STOP = "force_stop";
    public static final String MODE_DISABLE = "disable";
    public static final String MODE_CLEAR_CACHE = "clear_cache";

    // Sub-steps inside Settings -> App Info
    public static final int STEP_IDLE = 0;
    public static final int STEP_WAIT_APP_INFO = 1;
    public static final int STEP_WAIT_CONFIRM_DIALOG = 2;
    public static final int STEP_WAIT_STORAGE_SCREEN = 3;
    public static final int STEP_DONE_PACKAGE = 4;

    // Outcomes reported by the accessibility service
    public static final int OUTCOME_SUCCESS = QueuePlanner.OUTCOME_SUCCESS;
    public static final int OUTCOME_SKIPPED = QueuePlanner.OUTCOME_SKIPPED;
    public static final int OUTCOME_FAILED = QueuePlanner.OUTCOME_FAILED;

    private static final long NAV_SETTLE_MS = 380L;
    private static final long TIMEOUT_FIRST_PAGE_MS = 4600L;
    private static final long TIMEOUT_STEP_MS = 3600L;

    private static final String CHANNEL_ID = "annecontrol_run";
    private static final int NOTIFICATION_ID = 4001;

    private static final AutomationEngine INSTANCE = new AutomationEngine();

    public static AutomationEngine get() {
        return INSTANCE;
    }

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final List<String> labels = new ArrayList<String>();

    private QueuePlanner plan = new QueuePlanner(Collections.<String>emptyList(), true);
    private String mode = MODE_NONE;
    private int step = STEP_IDLE;
    private boolean running = false;
    private String statusMessage = "Idle";
    private String lastSummary = null;
    private int generation = 0;
    private long stepStartedAt = 0L;
    private Context appContext;

    private final Runnable timeoutRunnable = new Runnable() {
        @Override
        public void run() {
            synchronized (AutomationEngine.this) {
                if (!running) return;
                advanceInternal(OUTCOME_FAILED, "timed out waiting for the Settings screen");
            }
        }
    };

    public synchronized void start(Context ctx, String requestedMode, List<String> packages) {
        if (!MODE_FORCE_STOP.equals(requestedMode)
                && !MODE_DISABLE.equals(requestedMode)
                && !MODE_CLEAR_CACHE.equals(requestedMode)) {
            statusMessage = "Unknown mode: " + requestedMode;
            return;
        }

        // Invalidates every callback queued by a previous run before we touch state.
        generation++;
        handler.removeCallbacksAndMessages(null);

        this.appContext = ctx.getApplicationContext();
        this.plan = new QueuePlanner(packages, !MODE_CLEAR_CACHE.equals(requestedMode));

        this.labels.clear();
        List<String> packagesIn = plan.packages();
        for (int i = 0; i < packagesIn.size(); i++) {
            labels.add(resolveLabel(packagesIn.get(i)));
        }

        if (plan.isEmpty()) {
            running = false;
            mode = MODE_NONE;
            setStepInternal(STEP_IDLE);
            statusMessage = plan.summary();
            lastSummary = statusMessage;
            cancelNotification();
            return;
        }

        this.mode = requestedMode;
        this.running = true;
        this.lastSummary = null;
        openCurrentPackageSettings(generation);
    }

    /** User-initiated cancel (back button in-app, the notification, or Volume Down). */
    public synchronized void stop() {
        handler.removeCallbacksAndMessages(null);
        cancelNotification();
        if (!running) {
            return;
        }
        running = false;
        mode = MODE_NONE;
        setStepInternal(STEP_IDLE);
        lastSummary = "Cancelled after " + plan.processed() + " of " + plan.size() + " apps.";
        statusMessage = lastSummary;
        returnToApp();
    }

    public synchronized boolean isRunning() {
        return running;
    }

    public synchronized String getMode() {
        return mode;
    }

    public synchronized int getStep() {
        return step;
    }

    /**
     * Called when a step transition happens because something was actually done;
     * re-arms the "nothing happened" safety timeout for the new step.
     */
    public synchronized void setStep(int nextStep) {
        setStepInternal(nextStep);
        handler.removeCallbacks(timeoutRunnable);
        if (running) {
            handler.postDelayed(timeoutRunnable, TIMEOUT_STEP_MS);
        }
    }

    private void setStepInternal(int nextStep) {
        this.step = nextStep;
        this.stepStartedAt = SystemClock.elapsedRealtime();
    }

    /**
     * How long the current step has been waiting. Used by the accessibility service
     * to allow a page to render before deciding a screen mismatch is real.
     */
    public synchronized long getStepElapsedMs() {
        if (stepStartedAt <= 0L) return 0L;
        return SystemClock.elapsedRealtime() - stepStartedAt;
    }

    public synchronized String getCurrentPackage() {
        if (!running) return "";
        String current = plan.current();
        return current == null ? "" : current;
    }

    /**
     * Display name of the package currently being processed. The accessibility
     * service uses it to verify that the visible Settings page really belongs to
     * the app it is about to force-stop / disable.
     */
    public synchronized String getExpectedLabel() {
        if (!running) return "";
        int index = plan.index();
        if (index < 0 || index >= labels.size()) return "";
        return labels.get(index);
    }

    public synchronized int getCurrentIndex() {
        return plan.index();
    }

    public synchronized int getTotalCount() {
        return plan.size();
    }

    public synchronized int getSuccessCount() {
        return plan.successes();
    }

    public synchronized int getSkippedCount() {
        return plan.skipped();
    }

    public synchronized int getFailedCount() {
        return plan.failures();
    }

    public synchronized String getStatusMessage() {
        return statusMessage;
    }

    /** One-shot: returns the summary of the last finished run, then clears it. */
    public synchronized String consumeSummary() {
        String s = lastSummary;
        lastSummary = null;
        return s;
    }

    public synchronized void markPackageSuccessAndAdvance() {
        advanceInternal(OUTCOME_SUCCESS, null);
    }

    public synchronized void markPackageSkippedAndAdvance() {
        advanceInternal(OUTCOME_SKIPPED, null);
    }

    public synchronized void markPackageFailedAndAdvance(String why) {
        advanceInternal(OUTCOME_FAILED, why);
    }

    public synchronized void advanceToNextPackage() {
        advanceInternal(OUTCOME_SKIPPED, null);
    }

    /** Abort the whole run: used when the UI cannot be verified, so nothing unsafe happens. */
    public synchronized void abortRun(String reason) {
        if (!running) return;
        handler.removeCallbacksAndMessages(null);
        running = false;
        mode = MODE_NONE;
        setStepInternal(STEP_IDLE);
        lastSummary = "Aborted after " + plan.processed() + " of " + plan.size()
                + " apps: " + reason;
        statusMessage = lastSummary;
        cancelNotification();
        AnneAccessibilityService svc = AnneAccessibilityService.getInstance();
        if (svc != null) svc.pressBack();
        returnToApp();
    }

    private void advanceInternal(int outcome, String detail) {
        if (!running) return;
        handler.removeCallbacksAndMessages(null);

        plan.completeCurrent(outcome);

        // Leave the current App info page behind so the next intent cannot open on
        // top of a stale screen (an earlier version just navigated away).
        AnneAccessibilityService svc = AnneAccessibilityService.getInstance();
        if (svc != null) svc.pressBack();

        if (plan.finished()) {
            finishRun();
            return;
        }

        setStepInternal(STEP_IDLE);
        final int gen = generation;
        handler.postDelayed(new Runnable() {
            @Override
            public void run() {
                synchronized (AutomationEngine.this) {
                    if (!running || gen != generation) return;
                }
                openCurrentPackageSettings(gen);
            }
        }, NAV_SETTLE_MS);
    }

    private void finishRun() {
        running = false;
        mode = MODE_NONE;
        setStepInternal(STEP_IDLE);
        lastSummary = plan.summary();
        statusMessage = lastSummary;
        cancelNotification();
        returnToApp();
    }

    private void openCurrentPackageSettings(int gen) {
        String pkg;
        synchronized (this) {
            if (!running || appContext == null || gen != generation) {
                return;
            }
            pkg = plan.current();
            if (pkg == null) {
                return;
            }
            String label = getExpectedLabel();
            if (label.length() == 0) label = pkg;
            statusMessage = "Processing (" + (plan.index() + 1) + "/" + plan.size() + "): " + label;
            setStepInternal(STEP_WAIT_APP_INFO);
            handler.removeCallbacks(timeoutRunnable);
            handler.postDelayed(timeoutRunnable, TIMEOUT_FIRST_PAGE_MS);
        }
        showProgressNotification();
        try {
            Intent intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
            intent.setData(Uri.parse("package:" + pkg));
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
            appContext.startActivity(intent);
        } catch (Exception e) {
            advanceInternal(OUTCOME_FAILED, "could not open app info");
        }
    }

    private String resolveLabel(String pkg) {
        if (appContext == null) return pkg;
        try {
            PackageManager pm = appContext.getPackageManager();
            ApplicationInfo ai = pm.getApplicationInfo(pkg, 0);
            CharSequence label = pm.getApplicationLabel(ai);
            if (label != null && label.length() > 0) return label.toString();
        } catch (Exception ignored) {
        }
        return pkg;
    }

    private void returnToApp() {
        if (appContext == null) return;
        try {
            Intent backIntent = new Intent(appContext, MainActivity.class);
            backIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK
                    | Intent.FLAG_ACTIVITY_SINGLE_TOP
                    | Intent.FLAG_ACTIVITY_CLEAR_TOP);
            appContext.startActivity(backIntent);
        } catch (Exception ignored) {
        }
    }

    // ---------------------------------------------------------------- notification

    private NotificationManager notificationManager() {
        if (appContext == null) return null;
        return (NotificationManager) appContext.getSystemService(Context.NOTIFICATION_SERVICE);
    }

    private void showProgressNotification() {
        if (appContext == null) return;
        NotificationManager nm = notificationManager();
        if (nm == null) return;
        try {
            // minSdk is 26, so a channel always exists.
            NotificationChannel ch = new NotificationChannel(
                    CHANNEL_ID, "Automation progress", NotificationManager.IMPORTANCE_LOW);
            ch.setShowBadge(false);
            ch.setSound(null, null);
            nm.createNotificationChannel(ch);

            Intent stopIntent = new Intent(appContext, StopAutomationReceiver.class);
            stopIntent.setAction(StopAutomationReceiver.ACTION_STOP);
            PendingIntent stopPi = PendingIntent.getBroadcast(
                    appContext, 0, stopIntent,
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

            Notification.Builder b = new Notification.Builder(appContext, CHANNEL_ID);
            b.setSmallIcon(android.R.drawable.stat_notify_sync)
                    .setContentTitle("AnneControl is automating Settings")
                    .setContentText(statusMessage)
                    .setOngoing(true)
                    .setOnlyAlertOnce(true)
                    .addAction(new Notification.Action.Builder(
                            Icon.createWithResource(appContext, android.R.drawable.ic_menu_close_clear_cancel),
                            "STOP", stopPi).build());

            int total = plan.size();
            if (total > 0 && plan.index() < total) {
                b.setProgress(total, plan.index(), false);
            }
            nm.notify(NOTIFICATION_ID, b.build());
        } catch (Exception ignored) {
        }
    }

    private void cancelNotification() {
        NotificationManager nm = notificationManager();
        if (nm == null) return;
        try {
            nm.cancel(NOTIFICATION_ID);
        } catch (Exception ignored) {
        }
    }
}
