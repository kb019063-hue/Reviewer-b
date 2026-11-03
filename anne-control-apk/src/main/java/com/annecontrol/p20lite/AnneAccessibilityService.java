package com.annecontrol.p20lite;

import android.accessibilityservice.AccessibilityService;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;

import java.util.List;
import java.util.Locale;

public class AnneAccessibilityService extends AccessibilityService {

    private static volatile boolean serviceConnected = false;
    private long lastActionTimeMs = 0L;

    public static boolean isServiceConnected() {
        return serviceConnected;
    }

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        serviceConnected = true;
    }

    @Override
    public boolean onUnbind(android.content.Intent intent) {
        serviceConnected = false;
        return super.onUnbind(intent);
    }

    @Override
    public void onInterrupt() {
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        AutomationEngine engine = AutomationEngine.get();
        if (!engine.isRunning()) {
            return;
        }

        long now = System.currentTimeMillis();
        if (now - lastActionTimeMs < 280L) {
            return;
        }

        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) {
            return;
        }

        try {
            String mode = engine.getMode();
            int step = engine.getStep();

            if (AutomationEngine.MODE_FORCE_STOP.equals(mode)) {
                handleForceStop(root, engine, step);
            } else if (AutomationEngine.MODE_DISABLE.equals(mode)) {
                handleDisable(root, engine, step);
            } else if (AutomationEngine.MODE_CLEAR_CACHE.equals(mode)) {
                handleClearCache(root, engine, step);
            }
        } finally {
            root.recycle();
        }
    }

    private void handleForceStop(AccessibilityNodeInfo root, AutomationEngine engine, int step) {
        if (step == AutomationEngine.STEP_WAIT_APP_INFO) {
            AccessibilityNodeInfo btn = findClickableByExactLabels(root, new String[] { "force stop" });
            if (btn != null) {
                if (!btn.isEnabled()) {
                    // Already stopped!
                    engine.advanceToNextPackage();
                    return;
                }
                if (performClick(btn)) {
                    lastActionTimeMs = System.currentTimeMillis();
                    engine.setStep(AutomationEngine.STEP_WAIT_CONFIRM_DIALOG);
                }
            }
        } else if (step == AutomationEngine.STEP_WAIT_CONFIRM_DIALOG) {
            AccessibilityNodeInfo confirmBtn = findDialogConfirmButton(root, new String[] { "force stop", "ok" });
            if (confirmBtn != null && performClick(confirmBtn)) {
                lastActionTimeMs = System.currentTimeMillis();
                engine.markPackageSuccessAndAdvance();
            }
        }
    }

    private void handleDisable(AccessibilityNodeInfo root, AutomationEngine engine, int step) {
        if (step == AutomationEngine.STEP_WAIT_APP_INFO) {
            // Check if already disabled ("Enable" button shown)
            AccessibilityNodeInfo enableBtn = findClickableByExactLabels(root, new String[] { "enable" });
            if (enableBtn != null) {
                engine.advanceToNextPackage();
                return;
            }

            AccessibilityNodeInfo disableBtn = findClickableByExactLabels(root, new String[] { "disable" });
            if (disableBtn != null && disableBtn.isEnabled()) {
                if (performClick(disableBtn)) {
                    lastActionTimeMs = System.currentTimeMillis();
                    engine.setStep(AutomationEngine.STEP_WAIT_CONFIRM_DIALOG);
                    return;
                }
            }

            // If EMUI grays out Disable on a factory stub, fall back to Force Stop so RAM is still freed!
            AccessibilityNodeInfo forceBtn = findClickableByExactLabels(root, new String[] { "force stop" });
            if (forceBtn != null && forceBtn.isEnabled()) {
                if (performClick(forceBtn)) {
                    lastActionTimeMs = System.currentTimeMillis();
                    engine.setStep(AutomationEngine.STEP_WAIT_CONFIRM_DIALOG);
                    return;
                }
            }
        } else if (step == AutomationEngine.STEP_WAIT_CONFIRM_DIALOG) {
            AccessibilityNodeInfo confirmBtn = findDialogConfirmButton(
                    root,
                    new String[] { "disable app", "disable", "force stop", "ok" }
            );
            if (confirmBtn != null && performClick(confirmBtn)) {
                lastActionTimeMs = System.currentTimeMillis();
                engine.markPackageSuccessAndAdvance();
            }
        }
    }

    private void handleClearCache(AccessibilityNodeInfo root, AutomationEngine engine, int step) {
        // First check if "Clear cache" button is already on screen (Storage sub-page or direct layout)
        AccessibilityNodeInfo clearCacheBtn = findClickableByExactLabels(root, new String[] { "clear cache" });
        if (clearCacheBtn != null) {
            if (!clearCacheBtn.isEnabled()) {
                performGlobalAction(GLOBAL_ACTION_BACK);
                engine.advanceToNextPackage();
                return;
            }
            if (performClick(clearCacheBtn)) {
                lastActionTimeMs = System.currentTimeMillis();
                performGlobalAction(GLOBAL_ACTION_BACK);
                engine.markPackageSuccessAndAdvance();
            }
            return;
        }

        if (step == AutomationEngine.STEP_WAIT_APP_INFO) {
            AccessibilityNodeInfo storageRow = findClickableContainingLabels(
                    root,
                    new String[] { "storage", "storage & cache" }
            );
            if (storageRow != null && performClick(storageRow)) {
                lastActionTimeMs = System.currentTimeMillis();
                engine.setStep(AutomationEngine.STEP_WAIT_STORAGE_SCREEN);
            }
        }
    }

    private boolean isForbiddenLabel(String lower) {
        return lower.contains("clear data")
                || lower.contains("clear storage")
                || lower.contains("delete")
                || lower.contains("uninstall")
                || lower.contains("reset");
    }

    private AccessibilityNodeInfo findClickableByExactLabels(AccessibilityNodeInfo root, String[] targets) {
        for (int i = 0; i < targets.length; i++) {
            List<AccessibilityNodeInfo> list = root.findAccessibilityNodeInfosByText(targets[i]);
            if (list == null) continue;
            for (int j = 0; j < list.size(); j++) {
                AccessibilityNodeInfo node = list.get(j);
                if (node == null || node.getText() == null) continue;
                String text = node.getText().toString().trim().toLowerCase(Locale.US);
                if (isForbiddenLabel(text)) continue;
                if (text.equals(targets[i])) {
                    AccessibilityNodeInfo clickable = resolveClickableParent(node);
                    if (clickable != null) return clickable;
                }
            }
        }
        return null;
    }

    private AccessibilityNodeInfo findClickableContainingLabels(AccessibilityNodeInfo root, String[] targets) {
        for (int i = 0; i < targets.length; i++) {
            List<AccessibilityNodeInfo> list = root.findAccessibilityNodeInfosByText(targets[i]);
            if (list == null) continue;
            for (int j = 0; j < list.size(); j++) {
                AccessibilityNodeInfo node = list.get(j);
                if (node == null || node.getText() == null) continue;
                String text = node.getText().toString().trim().toLowerCase(Locale.US);
                if (isForbiddenLabel(text)) continue;
                if (text.equals(targets[i]) || text.startsWith(targets[i])) {
                    AccessibilityNodeInfo clickable = resolveClickableParent(node);
                    if (clickable != null) return clickable;
                }
            }
        }
        return null;
    }

    private AccessibilityNodeInfo findDialogConfirmButton(AccessibilityNodeInfo root, String[] labels) {
        // Prefer standard Android / EMUI AlertDialog positive button (android:id/button1)
        List<AccessibilityNodeInfo> byId = root.findAccessibilityNodeInfosByViewId("android:id/button1");
        if (byId != null && !byId.isEmpty()) {
            AccessibilityNodeInfo btn1 = byId.get(0);
            if (btn1 != null && btn1.getText() != null) {
                String txt = btn1.getText().toString().trim().toLowerCase(Locale.US);
                if (!isForbiddenLabel(txt) && btn1.isClickable() && btn1.isEnabled()) {
                    return btn1;
                }
            }
        }
        return findClickableByExactLabels(root, labels);
    }

    private AccessibilityNodeInfo resolveClickableParent(AccessibilityNodeInfo node) {
        AccessibilityNodeInfo cur = node;
        int depth = 0;
        while (cur != null && depth < 5) {
            if (cur.isClickable()) {
                return cur;
            }
            cur = cur.getParent();
            depth++;
        }
        return null;
    }

    private boolean performClick(AccessibilityNodeInfo node) {
        return node != null && node.performAction(AccessibilityNodeInfo.ACTION_CLICK);
    }
}
