package com.annecontrol.p20lite;

import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;

import java.util.ArrayList;
import java.util.List;

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

    private static final AutomationEngine INSTANCE = new AutomationEngine();

    public static AutomationEngine get() {
        return INSTANCE;
    }

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final List<String> queue = new ArrayList<String>();
    private String mode = MODE_NONE;
    private int currentIndex = 0;
    private int step = STEP_IDLE;
    private boolean running = false;
    private int succeededCount = 0;
    private String statusMessage = "Idle";
    private Context appContext;

    private final Runnable timeoutRunnable = new Runnable() {
        @Override
        public void run() {
            if (!running) return;
            // Safety timeout if button is already disabled/grayed out on EMUI 9.1
            advanceToNextPackage();
        }
    };

    public synchronized void start(Context ctx, String requestedMode, List<String> packages) {
        this.appContext = ctx.getApplicationContext();
        this.queue.clear();
        for (int i = 0; i < packages.size(); i++) {
            String p = packages.get(i);
            if (p != null && p.length() > 0) {
                if (!MODE_CLEAR_CACHE.equals(requestedMode) && HuaweiCatalog.isProtected(p)) {
                    continue;
                }
                this.queue.add(p);
            }
        }
        if (this.queue.isEmpty()) {
            this.running = false;
            this.statusMessage = "No eligible packages in queue.";
            return;
        }
        this.mode = requestedMode;
        this.currentIndex = 0;
        this.succeededCount = 0;
        this.running = true;
        openCurrentPackageSettings();
    }

    public synchronized void stop() {
        handler.removeCallbacks(timeoutRunnable);
        this.running = false;
        this.mode = MODE_NONE;
        this.step = STEP_IDLE;
        this.statusMessage = "Automation finished (" + succeededCount + " processed).";
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

    public synchronized void setStep(int nextStep) {
        this.step = nextStep;
        handler.removeCallbacks(timeoutRunnable);
        if (running) {
            handler.postDelayed(timeoutRunnable, 3400);
        }
    }

    public synchronized String getCurrentPackage() {
        if (!running || currentIndex < 0 || currentIndex >= queue.size()) {
            return "";
        }
        return queue.get(currentIndex);
    }

    public synchronized int getCurrentIndex() {
        return currentIndex;
    }

    public synchronized int getTotalCount() {
        return queue.size();
    }

    public synchronized int getSucceededCount() {
        return succeededCount;
    }

    public synchronized String getStatusMessage() {
        return statusMessage;
    }

    public synchronized void markPackageSuccessAndAdvance() {
        if (!running) return;
        succeededCount++;
        advanceToNextPackage();
    }

    public synchronized void advanceToNextPackage() {
        handler.removeCallbacks(timeoutRunnable);
        if (!running) return;
        currentIndex++;
        if (currentIndex >= queue.size()) {
            running = false;
            mode = MODE_NONE;
            step = STEP_IDLE;
            statusMessage = "Completed! Processed " + succeededCount + " of " + queue.size() + " apps.";
            returnToApp();
            return;
        }
        handler.postDelayed(new Runnable() {
            @Override
            public void run() {
                openCurrentPackageSettings();
            }
        }, 380);
    }

    private synchronized void openCurrentPackageSettings() {
        if (!running || appContext == null || currentIndex >= queue.size()) {
            return;
        }
        String pkg = queue.get(currentIndex);
        statusMessage = "Processing (" + (currentIndex + 1) + "/" + queue.size() + "): " + pkg;
        step = STEP_WAIT_APP_INFO;
        try {
            Intent intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
            intent.setData(Uri.parse("package:" + pkg));
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
            appContext.startActivity(intent);
            handler.removeCallbacks(timeoutRunnable);
            handler.postDelayed(timeoutRunnable, 3800);
        } catch (Exception e) {
            advanceToNextPackage();
        }
    }

    private void returnToApp() {
        if (appContext == null) return;
        try {
            Intent backIntent = new Intent(appContext, MainActivity.class);
            backIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
            appContext.startActivity(backIntent);
        } catch (Exception ignored) {
        }
    }
}
