package com.annecontrol.p20lite;

import android.accessibilityservice.AccessibilityService;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

public class AnneAccessibilityService extends AccessibilityService {

    private static volatile boolean serviceConnected = false;
    private long lastActionTimeMs = 0L;

    // Multilingual aliases for EMUI 9.1 buttons across EN, ES, FR, DE, IT, PT, RU, AR
    private static final String[] LABELS_FORCE_STOP = new String[] {
        "force stop", "forcer l'arrêt", "forzar detención", "beenden erzwingen",
        "arresto forzato", "forçar parada", "остановить", "إيقاف إجباري", "detener"
    };

    private static final String[] LABELS_DISABLE = new String[] {
        "disable", "disable app", "désactiver", "inhabilitar", "desactivar",
        "deaktivieren", "disattiva", "desativar", "отключить", "تعطيل"
    };

    private static final String[] LABELS_ENABLE = new String[] {
        "enable", "activer", "habilitar", "activar", "aktivieren", "attiva", "включить", "تفعيل"
    };

    private static final String[] LABELS_CLEAR_CACHE = new String[] {
        "clear cache", "vider le cache", "borrar caché", "cache leeren",
        "cancella cache", "limpar cache", "очистить кэш", "مسح ذاكرة التخزين المؤقت"
    };

    private static final String[] LABELS_STORAGE_ROW = new String[] {
        "storage", "storage & cache", "stockage", "almacenamiento", "speicher",
        "memoria", "armazenamento", "память", "وحدة التخزين"
    };

    private static final String[] LABELS_CONFIRM = new String[] {
        "ok", "force stop", "disable", "disable app", "yes", "oui", "sí", "ja",
        "désactiver", "inhabilitar", "desactivar", "остановить", "отключить", "موافق"
    };

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
            CharSequence rootPkg = root.getPackageName();
            // Verify active window belongs to Android Settings before acting
            if (rootPkg == null || !rootPkg.toString().contains("settings")) {
                return;
            }

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
            AccessibilityNodeInfo btn = findClickableByLabels(root, LABELS_FORCE_STOP, true);
            if (btn != null) {
                try {
                    if (!btn.isEnabled()) {
                        // Already stopped or not running!
                        engine.advanceToNextPackage();
                        return;
                    }
                    if (performClick(btn)) {
                        lastActionTimeMs = System.currentTimeMillis();
                        engine.setStep(AutomationEngine.STEP_WAIT_CONFIRM_DIALOG);
                    }
                } finally {
                    btn.recycle();
                }
            }
        } else if (step == AutomationEngine.STEP_WAIT_CONFIRM_DIALOG) {
            AccessibilityNodeInfo confirmBtn = findDialogConfirmButton(root, LABELS_CONFIRM);
            if (confirmBtn != null) {
                try {
                    if (performClick(confirmBtn)) {
                        lastActionTimeMs = System.currentTimeMillis();
                        engine.markPackageSuccessAndAdvance();
                    }
                } finally {
                    confirmBtn.recycle();
                }
            }
        }
    }

    private void handleDisable(AccessibilityNodeInfo root, AutomationEngine engine, int step) {
        if (step == AutomationEngine.STEP_WAIT_APP_INFO) {
            // Check if already disabled ("Enable" button shown)
            AccessibilityNodeInfo enableBtn = findClickableByLabels(root, LABELS_ENABLE, true);
            if (enableBtn != null) {
                enableBtn.recycle();
                engine.advanceToNextPackage();
                return;
            }

            AccessibilityNodeInfo disableBtn = findClickableByLabels(root, LABELS_DISABLE, true);
            if (disableBtn != null) {
                try {
                    if (disableBtn.isEnabled()) {
                        if (performClick(disableBtn)) {
                            lastActionTimeMs = System.currentTimeMillis();
                            engine.setStep(AutomationEngine.STEP_WAIT_CONFIRM_DIALOG);
                            return;
                        }
                    }
                } finally {
                    disableBtn.recycle();
                }
            }

            // Fallback: If EMUI grays out Disable on a stub, fall back to Force Stop
            AccessibilityNodeInfo forceBtn = findClickableByLabels(root, LABELS_FORCE_STOP, true);
            if (forceBtn != null) {
                try {
                    if (forceBtn.isEnabled()) {
                        if (performClick(forceBtn)) {
                            lastActionTimeMs = System.currentTimeMillis();
                            engine.setStep(AutomationEngine.STEP_WAIT_CONFIRM_DIALOG);
                            return;
                        }
                    }
                } finally {
                    forceBtn.recycle();
                }
            }
        } else if (step == AutomationEngine.STEP_WAIT_CONFIRM_DIALOG) {
            AccessibilityNodeInfo confirmBtn = findDialogConfirmButton(root, LABELS_CONFIRM);
            if (confirmBtn != null) {
                try {
                    if (performClick(confirmBtn)) {
                        lastActionTimeMs = System.currentTimeMillis();
                        engine.markPackageSuccessAndAdvance();
                    }
                } finally {
                    confirmBtn.recycle();
                }
            }
        }
    }

    private void handleClearCache(AccessibilityNodeInfo root, AutomationEngine engine, int step) {
        // First check if "Clear cache" button is already on screen (Storage sub-page or direct layout)
        AccessibilityNodeInfo clearCacheBtn = findClickableByLabels(root, LABELS_CLEAR_CACHE, true);
        if (clearCacheBtn != null) {
            try {
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
            } finally {
                clearCacheBtn.recycle();
            }
            return;
        }

        if (step == AutomationEngine.STEP_WAIT_APP_INFO) {
            AccessibilityNodeInfo storageRow = findClickableByLabels(root, LABELS_STORAGE_ROW, false);
            if (storageRow != null) {
                try {
                    if (performClick(storageRow)) {
                        lastActionTimeMs = System.currentTimeMillis();
                        engine.setStep(AutomationEngine.STEP_WAIT_STORAGE_SCREEN);
                    }
                } finally {
                    storageRow.recycle();
                }
            }
        }
    }

    private boolean isForbiddenLabel(String lower) {
        return lower.contains("clear data")
                || lower.contains("clear storage")
                || lower.contains("effacer les données")
                || lower.contains("borrar datos")
                || lower.contains("daten löschen")
                || lower.contains("cancella dati")
                || lower.contains("limpar dados")
                || lower.contains("стерéть данные")
                || lower.contains("delete")
                || lower.contains("uninstall")
                || lower.contains("désinstaller")
                || lower.contains("desinstalar")
                || lower.contains("deinstallieren")
                || lower.contains("reset");
    }

    private AccessibilityNodeInfo findClickableByLabels(AccessibilityNodeInfo root, String[] targets, boolean exactMatch) {
        for (int i = 0; i < targets.length; i++) {
            List<AccessibilityNodeInfo> list = root.findAccessibilityNodeInfosByText(targets[i]);
            if (list == null) continue;
            try {
                for (int j = 0; j < list.size(); j++) {
                    AccessibilityNodeInfo node = list.get(j);
                    if (node == null || node.getText() == null) continue;
                    String text = node.getText().toString().trim().toLowerCase(Locale.US);
                    if (isForbiddenLabel(text)) continue;

                    boolean match = exactMatch ? text.equals(targets[i]) : (text.equals(targets[i]) || text.startsWith(targets[i]));
                    if (match) {
                        AccessibilityNodeInfo clickable = resolveClickableParent(node);
                        if (clickable != null) {
                            return clickable; // caller responsible for recycling returned node
                        }
                    }
                }
            } finally {
                for (int j = 0; j < list.size(); j++) {
                    AccessibilityNodeInfo n = list.get(j);
                    if (n != null) n.recycle();
                }
            }
        }
        return null;
    }

    private AccessibilityNodeInfo findDialogConfirmButton(AccessibilityNodeInfo root, String[] labels) {
        // 1. Prefer standard Android / EMUI AlertDialog positive button (android:id/button1)
        List<AccessibilityNodeInfo> byId = root.findAccessibilityNodeInfosByViewId("android:id/button1");
        if (byId != null) {
            try {
                if (!byId.isEmpty()) {
                    AccessibilityNodeInfo btn1 = byId.get(0);
                    if (btn1 != null) {
                        CharSequence txt = btn1.getText();
                        String str = txt != null ? txt.toString().trim().toLowerCase(Locale.US) : "";
                        if (!isForbiddenLabel(str) && btn1.isClickable() && btn1.isEnabled()) {
                            // Obtain a fresh reference to return
                            return AccessibilityNodeInfo.obtain(btn1);
                        }
                    }
                }
            } finally {
                for (int i = 0; i < byId.size(); i++) {
                    if (byId.get(i) != null) byId.get(i).recycle();
                }
            }
        }

        // 2. Fall back to multilingual labels
        return findClickableByLabels(root, labels, true);
    }

    private AccessibilityNodeInfo resolveClickableParent(AccessibilityNodeInfo node) {
        AccessibilityNodeInfo cur = AccessibilityNodeInfo.obtain(node);
        int depth = 0;
        while (cur != null && depth < 5) {
            if (cur.isClickable()) {
                return cur;
            }
            AccessibilityNodeInfo parent = cur.getParent();
            cur.recycle();
            cur = parent;
            depth++;
        }
        if (cur != null) {
            cur.recycle();
        }
        return null;
    }

    private boolean performClick(AccessibilityNodeInfo node) {
        return node != null && node.performAction(AccessibilityNodeInfo.ACTION_CLICK);
    }
}
