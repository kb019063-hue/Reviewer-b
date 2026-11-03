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
        ws.setAllowFileAccess(true);
        ws.setTextZoom(100);

        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient());
        webView.addJavascriptInterface(new SystemBridge(getApplicationContext()), "AnneNative");

        setContentView(webView);
        webView.loadUrl("file:///android_asset/index.html");
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (webView != null) {
            webView.evaluateJavascript("window.onAnneResume && window.onAnneResume();", null);
        }
    }

    @Override
    public void onBackPressed() {
        if (AutomationEngine.get().isRunning()) {
            AutomationEngine.get().stop();
            if (webView != null) {
                webView.evaluateJavascript("window.onAnneResume && window.onAnneResume();", null);
            }
            return;
        }
        super.onBackPressed();
    }
}
