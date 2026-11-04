package com.annecontrol.p20lite;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * Plain-JVM tests for {@link QueuePlanner}.
 *
 * No JUnit: the build is a bare javac/d8 pipeline with no dependency resolution, so
 * this is a self-contained runner. ci_build.py compiles it against QueuePlanner and
 * HuaweiCatalog only (neither touches Android), runs it, and fails the APK build if
 * any assertion fails.
 *
 *     javac -d out src/main/java/.../HuaweiCatalog.java \
 *                    src/main/java/.../QueuePlanner.java \
 *                    test/java/.../QueuePlannerTest.java
 *     java -cp out com.annecontrol.p20lite.QueuePlannerTest
 */
public final class QueuePlannerTest {

    private static int passed = 0;
    private static int failed = 0;

    public static void main(String[] args) {
        System.out.println("QueuePlannerTest");

        deduplicatesAndTrims();
        dropsBlanksAndNulls();
        filtersProtectedTierForDestructiveModes();
        keepsProtectedTierForClearCache();
        preservesOrder();
        emptyQueueHasSensibleSummary();
        countersTrackOutcomes();
        unknownOutcomeCountsAsFailure();
        cannotOverrunTheQueue();
        currentIsNullOnceFinished();
        summaryReportsTheBreakdown();
        packageViewIsReadOnly();

        System.out.println();
        System.out.println(passed + " passed, " + failed + " failed");
        if (failed > 0) {
            System.exit(1);
        }
    }

    // ------------------------------------------------------------------ cases

    private static void deduplicatesAndTrims() {
        List<String> requested = Arrays.asList(" com.a ", "com.a", "com.b", "com.b");
        QueuePlanner plan = new QueuePlanner(requested, false);
        eq("trims and de-duplicates", 2, plan.size());
        eq("keeps the first occurrence", "com.a", plan.current());
    }

    private static void dropsBlanksAndNulls() {
        List<String> requested = new ArrayList<String>();
        requested.add(null);
        requested.add("");
        requested.add("   ");
        requested.add("com.a");
        QueuePlanner plan = new QueuePlanner(requested, false);
        eq("drops null/blank entries", 1, plan.size());
        check("null list yields an empty plan", new QueuePlanner(null, false).isEmpty());
    }

    private static void filtersProtectedTierForDestructiveModes() {
        // com.google.android.gms is tier "protected" in HuaweiCatalog
        List<String> requested = Arrays.asList("com.google.android.gms", "com.huawei.search");
        QueuePlanner plan = new QueuePlanner(requested, true);
        eq("protected package dropped for disable/force-stop", 1, plan.size());
        eq("the safe package survives", "com.huawei.search", plan.current());
    }

    private static void keepsProtectedTierForClearCache() {
        List<String> requested = Arrays.asList("com.google.android.gms", "com.huawei.search");
        QueuePlanner plan = new QueuePlanner(requested, false);
        eq("protected package kept for clear-cache", 2, plan.size());
    }

    private static void preservesOrder() {
        QueuePlanner plan = new QueuePlanner(Arrays.asList("c", "a", "b"), false);
        eq("order preserved", Arrays.asList("c", "a", "b"), plan.packages());
    }

    private static void emptyQueueHasSensibleSummary() {
        QueuePlanner plan = new QueuePlanner(new ArrayList<String>(), false);
        check("empty plan reports empty", plan.isEmpty());
        check("empty plan is finished", plan.finished());
        eq("empty summary", "No eligible packages in queue.", plan.summary());
        check("no current package", plan.current() == null);
    }

    private static void countersTrackOutcomes() {
        QueuePlanner plan = new QueuePlanner(Arrays.asList("a", "b", "c"), false);
        plan.completeCurrent(QueuePlanner.OUTCOME_SUCCESS);
        plan.completeCurrent(QueuePlanner.OUTCOME_SKIPPED);
        eq("index advances", 2, plan.index());
        eq("successes", 1, plan.successes());
        eq("skipped", 1, plan.skipped());
        eq("processed", 2, plan.processed());
        eq("nothing failed yet", 0, plan.failures());
        check("still has work", !plan.finished());
        eq("next package", "c", plan.current());

        plan.completeCurrent(QueuePlanner.OUTCOME_FAILED);
        eq("failures", 1, plan.failures());
        check("finished after the last package", plan.finished());
    }

    private static void unknownOutcomeCountsAsFailure() {
        QueuePlanner plan = new QueuePlanner(Arrays.asList("a"), false);
        plan.completeCurrent(99);
        eq("unknown outcome is not counted as success", 0, plan.successes());
        eq("unknown outcome is a failure", 1, plan.failures());
    }

    private static void cannotOverrunTheQueue() {
        QueuePlanner plan = new QueuePlanner(Arrays.asList("a"), false);
        plan.completeCurrent(QueuePlanner.OUTCOME_SUCCESS);
        plan.completeCurrent(QueuePlanner.OUTCOME_SUCCESS);
        plan.completeCurrent(QueuePlanner.OUTCOME_SUCCESS);
        eq("extra advances do not inflate counters", 1, plan.processed());
        eq("index stops at the end", 1, plan.index());
    }

    private static void currentIsNullOnceFinished() {
        QueuePlanner plan = new QueuePlanner(Arrays.asList("a"), false);
        plan.completeCurrent(QueuePlanner.OUTCOME_SKIPPED);
        check("current() is null after the end", plan.current() == null);
    }

    private static void summaryReportsTheBreakdown() {
        QueuePlanner plan = new QueuePlanner(Arrays.asList("a", "b", "c"), false);
        plan.completeCurrent(QueuePlanner.OUTCOME_SUCCESS);
        plan.completeCurrent(QueuePlanner.OUTCOME_SKIPPED);
        plan.completeCurrent(QueuePlanner.OUTCOME_FAILED);
        String summary = plan.summary();
        check("summary counts a success", summary.contains("1 succeeded"));
        check("summary counts a skip", summary.contains("1 skipped"));
        check("summary counts a failure", summary.contains("1 failed"));
        check("summary states the total", summary.contains("of 3 apps"));
    }

    private static void packageViewIsReadOnly() {
        QueuePlanner plan = new QueuePlanner(Arrays.asList("a"), false);
        boolean threw = false;
        try {
            plan.packages().add("b");
        } catch (UnsupportedOperationException expected) {
            threw = true;
        }
        check("packages() view cannot be mutated", threw);
    }

    // ------------------------------------------------------------ assertions

    private static void check(String name, boolean condition) {
        if (condition) {
            passed++;
            System.out.println("  PASS  " + name);
        } else {
            failed++;
            System.out.println("  FAIL  " + name);
        }
    }

    private static void eq(String name, Object expected, Object actual) {
        boolean same = expected == null ? actual == null : expected.equals(actual);
        if (same) {
            check(name, true);
        } else {
            failed++;
            System.out.println("  FAIL  " + name + " (expected <" + expected + ">, got <" + actual + ">)");
        }
    }

    private QueuePlannerTest() {
    }
}
