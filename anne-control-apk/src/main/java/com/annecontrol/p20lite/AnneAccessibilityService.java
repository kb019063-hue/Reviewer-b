package com.annecontrol.p20lite;

import android.accessibilityservice.AccessibilityService;
import android.os.SystemClock;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Clicks through App info / Storage / confirm dialogs in Settings.
 *
 * Safety model (docs/CODE_REVIEW.md 1.2): a click is only performed once the
 * visible screen has been verified to belong to the package the engine is
 * currently working on. Verification compares the app's display label (and its
 * package id) against the text/content-description actually present in the
 * window. If the screen cannot be verified after a short grace period the run is
 * aborted instead of clicking something unknown.
 *
 * The previous version only checked that the window belonged to a package whose
 * name contains "settings", which is true of every Settings screen - including
 * the App info page of a completely different app.
 */
public class AnneAccessibilityService extends AccessibilityService {

    /** Mismatching events needed (inside one burst) before we give up on a screen. */
    private static final int MAX_MISMATCHES = 6;
    /** A burst has to last at least this long before it counts, so page load is not a mismatch. */
    private static final long MISMATCH_BURST_MS = 1500L;
    /** Consecutive unverifiable packages before the whole run is aborted. */
    private static final int MAX_UNVERIFIED_PACKAGES = 3;
    /** Bound on nodes created by a single tree walk, so a pathological tree cannot stall us. */
    private static final int MAX_NODES = 900;
    /** Grace period after a step starts, while the Settings page is still rendering. */
    private static final long VERIFY_GRACE_MS = 1800L;

    private static volatile boolean serviceConnected = false;
    private static volatile AnneAccessibilityService instance = null;

    private long lastActionTimeMs = 0L;
    private int consecutiveMismatches = 0;
    private long mismatchBurstStartedAt = 0L;
    private int unverifiedPackages = 0;

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

    /**
     * Neutral "proceed" wording only. The old list also contained "force stop" and
     * "disable", which meant that with no dialog on screen the confirm step could
     * click the action button a second time and report it as success.
     */
    private static final String[] LABELS_CONFIRM_NEUTRAL = new String[] {
        "ok", "yes", "ja", "oui", "sí", "si", "موافق"
    };

    public static boolean isServiceConnected() {
        return serviceConnected;
    }

    public static AnneAccessibilityService getInstance() {
        return instance;
    }

    public void pressBack() {
        try {
            performGlobalAction(GLOBAL_ACTION_BACK);
        } catch (Exception ignored) {
        }
    }

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        instance = this;
        serviceConnected = true;
    }

    @Override
    public boolean onUnbind(android.content.Intent intent) {
        serviceConnected = false;
        instance = null;
        return super.onUnbind(intent);
    }

    @Override
    public void onDestroy() {
        serviceConnected = false;
        instance = null;
        super.onDestroy();
    }

    @Override
    public void onInterrupt() {
    }

    /**
     * Hardware escape hatch. While a run is driving Settings the app's own UI is
     * unreachable, so besides the notification STOP action we also cancel on
     * Volume Down. Only active during a run, and only consumed then, so normal
     * volume control is untouched. Requires the user to have allowed key filtering
     * for this service; if they have not, this is simply never called.
     */
    @Override
    protected boolean onKeyEvent(android.view.KeyEvent event) {
        AutomationEngine engine = AutomationEngine.get();
        if (engine.isRunning()
                && event.getAction() == android.view.KeyEvent.ACTION_DOWN
                && event.getKeyCode() == android.view.KeyEvent.KEYCODE_VOLUME_DOWN) {
            engine.stop();
            return true;
        }
        return super.onKeyEvent(event);
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

        int step = engine.getStep();
        if (step == AutomationEngine.STEP_IDLE) {
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

            // A dialog window does not contain the app header, so the identity
            // check only applies to the pages we navigate ourselves.
            if (step != AutomationEngine.STEP_WAIT_CONFIRM_DIALOG) {
                if (!verifyTargetScreen(root, engine)) {
                    noteMismatch(engine);
                    return;
                }
                resetVerificationState();
            }

            String mode = engine.getMode();
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

    // ------------------------------------------------------------------ identity

    /**
     * True only when the window really shows the app the engine queued up.
     * Fails closed: no match means no click.
     */
    private boolean verifyTargetScreen(AccessibilityNodeInfo root, AutomationEngine engine) {
        String expectedPkg = engine.getCurrentPackage();
        if (expectedPkg == null || expectedPkg.length() == 0) {
            return false;
        }
        String expectedLabel = engine.getExpectedLabel();
        if (expectedLabel != null && expectedLabel.length() > 0 && !expectedLabel.equals(expectedPkg)) {
            return windowHasExactText(root, new String[] { expectedLabel, expectedPkg });
        }
        return windowHasExactText(root, new String[] { expectedPkg });
    }

    /**
     * A screen we cannot verify is skipped rather than clicked. One unverifiable app
     * (odd label, missing header) must not destroy the whole run, but three such
     * packages in a row means something systematic is wrong - then we abort.
     */
    private void noteMismatch(AutomationEngine engine) {
        // Give the page time to render its header before treating a mismatch as
        // "this is not the app we asked for".
        if (engine.getStepElapsedMs() < VERIFY_GRACE_MS) {
            return;
        }
        long now = SystemClock.elapsedRealtime();
        if (mismatchBurstStartedAt == 0L || now - mismatchBurstStartedAt > 3000L) {
            mismatchBurstStartedAt = now;
            consecutiveMismatches = 0;
        }
        consecutiveMismatches++;
        if (consecutiveMismatches < MAX_MISMATCHES || now - mismatchBurstStartedAt < MISMATCH_BURST_MS) {
            return;
        }

        mismatchBurstStartedAt = 0L;
        consecutiveMismatches = 0;
        unverifiedPackages++;
        String pkg = engine.getCurrentPackage();
        if (unverifiedPackages >= MAX_UNVERIFIED_PACKAGES) {
            engine.abortRun("could not verify " + unverifiedPackages
                    + " Settings pages in a row - nothing was changed on them");
        } else {
            engine.markPackageFailedAndAdvance("could not verify the Settings page was " + pkg);
        }
    }

    private void resetVerificationState() {
        consecutiveMismatches = 0;
        mismatchBurstStartedAt = 0L;
        unverifiedPackages = 0;
    }

    /**
     * True when any of {@code candidates} appears on screen as exact (normalised)
     * text or content description. One tree walk for all candidates, instead of one
     * native subtree search per candidate.
     */
    private boolean windowHasExactText(AccessibilityNodeInfo root, String[] candidates) {
        final Set<String> wanted = new HashSet<String>();
        for (int i = 0; i < candidates.length; i++) {
            String n = normalize(candidates[i]);
            if (n.length() > 0) wanted.add(n);
        }
        if (wanted.isEmpty()) return false;

        final boolean[] found = new boolean[] { false };
        scanTree(root, new NodeVisitor() {
            @Override
            public boolean visit(AccessibilityNodeInfo node) {
                CharSequence text = node.getText();
                if (text != null && wanted.contains(normalize(text.toString()))) {
                    found[0] = true;
                    return true;
                }
                CharSequence desc = node.getContentDescription();
                if (desc != null && wanted.contains(normalize(desc.toString()))) {
                    found[0] = true;
                    return true;
                }
                return false;
            }
        });
        return found[0];
    }

    /**
     * Dialog guard: require at least one action-specific phrase anywhere in the
     * visible modal before selecting its positive button. Matching is normalised
     * and substring-based because localized prompts add surrounding words.
     */
    private boolean windowContainsAnyText(AccessibilityNodeInfo root, final String[] candidates) {
        final Set<String> wanted = new HashSet<String>();
        for (int i = 0; i < candidates.length; i++) {
            String n = normalize(candidates[i]);
            if (n.length() > 0) wanted.add(n);
        }
        final boolean[] found = new boolean[] { false };
        scanTree(root, new NodeVisitor() {
            @Override
            public boolean visit(AccessibilityNodeInfo node) {
                CharSequence text = node.getText();
                if (containsWanted(text, wanted)) {
                    found[0] = true;
                    return true;
                }
                if (containsWanted(node.getContentDescription(), wanted)) {
                    found[0] = true;
                    return true;
                }
                return false;
            }
        });
        return found[0];
    }

    private boolean containsWanted(CharSequence value, Set<String> wanted) {
        if (value == null) return false;
        String n = normalize(value.toString());
        for (String candidate : wanted) {
            if (n.contains(candidate)) return true;
        }
        return false;
    }

    /** Visitor for {@link #scanTree}; return true to stop the walk early. */
    private interface NodeVisitor {
        boolean visit(AccessibilityNodeInfo node);
    }

    /**
     * Breadth-first walk of the active window.
     *
     * The window is walked once regardless of how many labels we are looking for,
     * and the walk is bounded so a pathological tree cannot stall the service. All
     * nodes created by the walk are recycled before returning, so a visitor may not
     * retain a node reference past its own visit() call.
     */
    private void scanTree(AccessibilityNodeInfo root, NodeVisitor visitor) {
        if (root == null) return;
        List<AccessibilityNodeInfo> queue = new ArrayList<AccessibilityNodeInfo>();
        queue.add(AccessibilityNodeInfo.obtain(root));
        int head = 0;
        try {
            while (head < queue.size() && head < MAX_NODES) {
                AccessibilityNodeInfo node = queue.get(head++);
                if (visitor.visit(node)) return;
                int childCount = node.getChildCount();
                for (int i = 0; i < childCount && queue.size() < MAX_NODES; i++) {
                    AccessibilityNodeInfo child = node.getChild(i);
                    if (child != null) queue.add(child);
                }
            }
        } finally {
            recycleAll(queue);
        }
    }

    private String normalize(String s) {
        if (s == null) return "";
        String lower = s.toLowerCase(Locale.US);
        StringBuilder sb = new StringBuilder(lower.length());
        for (int i = 0; i < lower.length(); i++) {
            char c = lower.charAt(i);
            if (Character.isLetterOrDigit(c)) sb.append(c);
        }
        return sb.toString();
    }

    // -------------------------------------------------------------------- modes

    private void handleForceStop(AccessibilityNodeInfo root, AutomationEngine engine, int step) {
        if (step == AutomationEngine.STEP_WAIT_APP_INFO) {
            AccessibilityNodeInfo btn = findClickableByLabels(root, LABELS_FORCE_STOP, true);
            if (btn != null) {
                try {
                    if (!btn.isEnabled()) {
                        // Already stopped or not running - nothing to do.
                        engine.markPackageSkippedAndAdvance();
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
            AccessibilityNodeInfo confirmBtn = findDialogConfirmButton(root, engine.getMode());
            if (confirmBtn != null) {
                try {
                    if (performClick(confirmBtn)) {
                        lastActionTimeMs = System.currentTimeMillis();
                        engine.setStep(AutomationEngine.STEP_VERIFY_FORCE_STOP);
                    }
                } finally {
                    confirmBtn.recycle();
                }
            }
        } else if (step == AutomationEngine.STEP_VERIFY_FORCE_STOP) {
            AccessibilityNodeInfo btn = findClickableByLabels(root, LABELS_FORCE_STOP, true);
            if (btn != null) {
                try {
                    if (!btn.isEnabled()) {
                        engine.markPackageSuccessAndAdvance();
                    }
                } finally {
                    btn.recycle();
                }
            }
        }
    }

    private void handleDisable(AccessibilityNodeInfo root, AutomationEngine engine, int step) {
        if (step == AutomationEngine.STEP_WAIT_APP_INFO) {
            // Already disabled? EMUI shows "Enable" instead of "Disable".
            AccessibilityNodeInfo enableBtn = findClickableByLabels(root, LABELS_ENABLE, true);
            if (enableBtn != null) {
                enableBtn.recycle();
                engine.markPackageSkippedAndAdvance();
                return;
            }

            AccessibilityNodeInfo disableBtn = findClickableByLabels(root, LABELS_DISABLE, true);
            if (disableBtn == null) {
                // Keep waiting for the page's controls to finish rendering; the step timeout
                // will report failure without substituting a different operation.
                return;
            }
            try {
                if (!disableBtn.isEnabled()) {
                    engine.markPackageFailedAndAdvance("Disable is unavailable; no fallback action was taken");
                } else if (performClick(disableBtn)) {
                    lastActionTimeMs = System.currentTimeMillis();
                    engine.setStep(AutomationEngine.STEP_WAIT_CONFIRM_DIALOG);
                }
            } finally {
                disableBtn.recycle();
            }
        } else if (step == AutomationEngine.STEP_WAIT_CONFIRM_DIALOG) {
            AccessibilityNodeInfo confirmBtn = findDialogConfirmButton(root, engine.getMode());
            if (confirmBtn != null) {
                try {
                    if (performClick(confirmBtn)) {
                        lastActionTimeMs = System.currentTimeMillis();
                        engine.setStep(AutomationEngine.STEP_VERIFY_DISABLE);
                    }
                } finally {
                    confirmBtn.recycle();
                }
            }
        } else if (step == AutomationEngine.STEP_VERIFY_DISABLE) {
            AccessibilityNodeInfo enableBtn = findClickableByLabels(root, LABELS_ENABLE, true);
            if (enableBtn != null) {
                enableBtn.recycle();
                engine.markPackageSuccessAndAdvance();
            }
        }
    }

    private void handleClearCache(AccessibilityNodeInfo root, AutomationEngine engine, int step) {
        if (step != AutomationEngine.STEP_WAIT_APP_INFO
                && step != AutomationEngine.STEP_WAIT_STORAGE_SCREEN
                && step != AutomationEngine.STEP_VERIFY_CACHE) {
            return;
        }

        AccessibilityNodeInfo clearCacheBtn = findClickableByLabels(root, LABELS_CLEAR_CACHE, true);
        if (clearCacheBtn != null) {
            try {
                if (step == AutomationEngine.STEP_VERIFY_CACHE) {
                    if (!clearCacheBtn.isEnabled()) {
                        engine.markPackageSuccessAndAdvance();
                    }
                    return;
                }
                if (!clearCacheBtn.isEnabled()) {
                    engine.markPackageSkippedAndAdvance();
                    return;
                }
                if (performClick(clearCacheBtn)) {
                    lastActionTimeMs = System.currentTimeMillis();
                    engine.setStep(AutomationEngine.STEP_VERIFY_CACHE);
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

    // ------------------------------------------------------------------- lookups

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

    /**
     * First clickable node whose text (or content description) matches one of
     * {@code targets}, preferring earlier entries in the array.
     *
     * This walks the window once and scores matches by label priority. The previous
     * implementation called findAccessibilityNodeInfosByText() per alias, i.e. up to
     * nine full native subtree searches per accessibility event - expensive enough to
     * jank the very Settings screen it was driving.
     *
     * Caller is responsible for recycling the returned node.
     */
    private AccessibilityNodeInfo findClickableByLabels(AccessibilityNodeInfo root, final String[] targets, final boolean exactMatch) {
        final AccessibilityNodeInfo[] best = new AccessibilityNodeInfo[] { null };
        final int[] bestIndex = new int[] { Integer.MAX_VALUE };

        scanTree(root, new NodeVisitor() {
            @Override
            public boolean visit(AccessibilityNodeInfo node) {
                int index = matchIndex(node, targets, exactMatch);
                if (index < 0 || index >= bestIndex[0]) return false;

                AccessibilityNodeInfo clickable = resolveClickableParent(node);
                if (clickable == null) return false;

                if (best[0] != null) best[0].recycle();
                best[0] = clickable;
                bestIndex[0] = index;
                return index == 0; // highest-priority alias already found
            }
        });
        return best[0];
    }

    private int matchIndex(AccessibilityNodeInfo node, String[] targets, boolean exactMatch) {
        String text = lower(node.getText());
        String desc = lower(node.getContentDescription());
        for (int i = 0; i < targets.length; i++) {
            if (matchesLabel(text, targets[i], exactMatch)
                    || matchesLabel(desc, targets[i], exactMatch)) {
                return i;
            }
        }
        return -1;
    }

    private String lower(CharSequence cs) {
        if (cs == null) return null;
        String s = cs.toString().trim().toLowerCase(Locale.US);
        return s.length() == 0 ? null : s;
    }

    private boolean matchesLabel(String value, String target, boolean exactMatch) {
        if (value == null) return false;
        if (isForbiddenLabel(value)) return false;
        if (value.equals(target)) return true;
        return !exactMatch && value.startsWith(target);
    }

    /**
     * Positive button of the confirmation dialog.
     *
     * Order matters: the platform id is unambiguous (AOSP AlertDialog, which EMUI
     * themes but keeps), then neutral wording, and only as a last resort the
     * action's own wording, since some EMUI builds label the positive button
     * "Force stop"/"Disable" instead of "OK".
     */
    private AccessibilityNodeInfo findDialogConfirmButton(AccessibilityNodeInfo root, String mode) {
        String[] actionLabels;
        if (AutomationEngine.MODE_FORCE_STOP.equals(mode)) {
            actionLabels = LABELS_FORCE_STOP;
        } else if (AutomationEngine.MODE_DISABLE.equals(mode)) {
            actionLabels = LABELS_DISABLE;
        } else {
            return null;
        }
        // A generic button1/OK is not enough: require the modal itself to mention
        // the action we just requested before confirming it.
        if (!windowContainsAnyText(root, actionLabels)) return null;

        AccessibilityNodeInfo byId = findClickableByViewId(root, "android:id/button1");
        if (byId != null) return byId;

        AccessibilityNodeInfo neutral = findClickableByLabels(root, LABELS_CONFIRM_NEUTRAL, true);
        if (neutral != null) return neutral;

        if (AutomationEngine.MODE_FORCE_STOP.equals(mode)) {
            return findClickableByLabels(root, LABELS_FORCE_STOP, true);
        }
        if (AutomationEngine.MODE_DISABLE.equals(mode)) {
            return findClickableByLabels(root, LABELS_DISABLE, true);
        }
        return null;
    }

    private AccessibilityNodeInfo findClickableByViewId(AccessibilityNodeInfo root, String viewId) {
        List<AccessibilityNodeInfo> byId = root.findAccessibilityNodeInfosByViewId(viewId);
        if (byId == null) return null;
        try {
            for (int i = 0; i < byId.size(); i++) {
                AccessibilityNodeInfo btn = byId.get(i);
                if (btn == null) continue;
                CharSequence txt = btn.getText();
                String str = txt != null ? txt.toString().trim().toLowerCase(Locale.US) : "";
                if (isForbiddenLabel(str)) continue;
                if (btn.isClickable() && btn.isEnabled()) {
                    return AccessibilityNodeInfo.obtain(btn);
                }
            }
        } finally {
            recycleAll(byId);
        }
        return null;
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

    private void recycleAll(List<AccessibilityNodeInfo> list) {
        if (list == null) return;
        for (int i = 0; i < list.size(); i++) {
            AccessibilityNodeInfo n = list.get(i);
            if (n != null) n.recycle();
        }
    }
}
