package com.annecontrol.p20lite;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/**
 * Backs the "STOP" action on the ongoing notification.
 *
 * While an automation run is active, Settings is on top of MainActivity, so the
 * user cannot reach the app's own UI (and therefore its back-button cancel).
 * This receiver is the escape hatch: it is reachable from the notification
 * shade the entire time a run is in flight.
 */
public class StopAutomationReceiver extends BroadcastReceiver {

    public static final String ACTION_STOP = "com.annecontrol.p20lite.action.STOP";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || !ACTION_STOP.equals(intent.getAction())) {
            return;
        }
        AutomationEngine.get().stop();
    }
}
