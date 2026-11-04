package com.annecontrol.p20lite;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Pure decision logic for one automation run: which packages are eligible, where
 * we are in the queue, and how the outcomes add up.
 *
 * Deliberately free of Android types so it can be compiled and exercised on a plain
 * JVM (see test/java/.../QueuePlannerTest.java, run by ci_build.py). Everything that
 * used to be tangled into AutomationEngine's Handler/Context state lives here.
 */
final class QueuePlanner {

    static final int OUTCOME_SUCCESS = 0;
    static final int OUTCOME_SKIPPED = 1;
    static final int OUTCOME_FAILED = 2;

    private final List<String> packages = new ArrayList<String>();
    private int index = 0;
    private int successes = 0;
    private int skipped = 0;
    private int failed = 0;

    /**
     * @param requested     packages as handed over by the UI (may contain blanks,
     *                      duplicates and nulls)
     * @param skipProtected drop the catalog's protected tier; false for clear-cache runs,
     *                      where touching a protected package's cache is harmless
     */
    QueuePlanner(List<String> requested, boolean skipProtected) {
        if (requested == null) return;
        for (int i = 0; i < requested.size(); i++) {
            String candidate = requested.get(i);
            if (candidate == null) continue;
            candidate = candidate.trim();
            if (candidate.length() == 0) continue;
            if (packages.contains(candidate)) continue;
            if (skipProtected && HuaweiCatalog.isProtected(candidate)) continue;
            packages.add(candidate);
        }
    }

    /** Eligible packages, in the order they will be processed. */
    List<String> packages() {
        return Collections.unmodifiableList(packages);
    }

    boolean isEmpty() {
        return packages.isEmpty();
    }

    int size() {
        return packages.size();
    }

    int index() {
        return index;
    }

    int successes() {
        return successes;
    }

    int skipped() {
        return skipped;
    }

    int failures() {
        return failed;
    }

    int processed() {
        return successes + skipped + failed;
    }

    boolean finished() {
        return index >= packages.size();
    }

    /** Package being processed, or null once the queue is exhausted. */
    String current() {
        return index >= 0 && index < packages.size() ? packages.get(index) : null;
    }

    /**
     * Records the outcome for the current package and advances. Unknown outcome
     * values are counted as failures rather than silently ignored, so a bad caller
     * shows up in the summary instead of inflating the success count.
     */
    void completeCurrent(int outcome) {
        if (finished()) return;
        if (outcome == OUTCOME_SUCCESS) {
            successes++;
        } else if (outcome == OUTCOME_SKIPPED) {
            skipped++;
        } else {
            failed++;
        }
        index++;
    }

    String summary() {
        if (packages.isEmpty()) return "No eligible packages in queue.";
        return "Done: " + successes + " succeeded, " + skipped + " skipped, "
                + failed + " failed of " + packages.size() + " apps.";
    }
}
