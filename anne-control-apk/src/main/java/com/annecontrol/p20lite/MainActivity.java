package com.annecontrol.p20lite;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {

    private static final String JS_RESUME = "window.onAnneResume && window.onAnneResume();";

    private WebView webView;

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        Window win = getWindow();
        if (win != null && Build.VERSION.SDK_INT >= 21) {
            win.setStatusBarColor(Color.parseColor("#020617"));
            win.setNavigationBarColor(Color.parseColor("#020617"));
        }

        webView = new WebView(this);
        webView.setBackgroundColor(Color.parseColor("#020617"));
        webView.setOverScrollMode(View.OVER_SCROLL_NEVER);

        WebSettings ws = webView.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setAllowFileAccess(false); // Secure against local storage traversal
        ws.setAllowContentAccess(false);
        ws.setTextZoom(100);

        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient());
        webView.addJavascriptInterface(new SystemBridge(this, webView), "AnneNative");

        setContentView(webView);

        // EMUI 9.1 kills backgrounded apps aggressively; if the process does go away
        // while the user is in Settings, restore the WebView instead of reloading it.
        boolean restored = false;
        if (savedInstanceState != null) {
            restored = webView.restoreState(savedInstanceState) != null;
        }
        if (!restored) {
            webView.loadUrl("file:///android_asset/index.html");
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        if (webView != null) {
            webView.saveState(outState);
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (webView != null) {
            webView.evaluateJavascript(JS_RESUME, null);
        }
    }

    @Override
    public void onBackPressed() {
        AutomationEngine engine = AutomationEngine.get();
        if (engine.isRunning()) {
            engine.stop();
            if (webView != null) {
                webView.evaluateJavascript(JS_RESUME, null);
            }
            return;
        }
        super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            try {
                webView.removeJavascriptInterface("AnneNative");
                webView.setWebChromeClient(null);
                webView.setWebViewClient(null);
                webView.destroy();
            } catch (Exception ignored) {
            }
            webView = null;
        }
        super.onDestroy();
    }
}
