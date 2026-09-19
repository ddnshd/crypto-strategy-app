package com.cryptostrategy;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import androidx.appcompat.app.AppCompatActivity;
public class MainActivity extends AppCompatActivity {
    private static final String TERMUX_PKG = "com.termux";
    private static final String BACKEND_DIR = "/data/data/com.termux/files/home/crypto-strategy-app/apps/backend";
    private WebView webView;
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        webView = findViewById(R.id.webview);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        // Wajib: halaman file:///android_asset/... perlu akses fetch/XHR ke backend http://127.0.0.1:8001
        settings.setAllowFileAccessFromFileURLs(true);
        settings.setAllowUniversalAccessFromFileURLs(true);
        settings.setMixedContentMode(android.webkit.WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        settings.setMediaPlaybackRequiresUserGesture(false);
        webView.setWebViewClient(new android.webkit.WebViewClient());
        webView.addJavascriptInterface(new BackendBridge(), "AndroidBackend");
        webView.loadUrl("file:///android_asset/webapp/index.html");
    }
    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) webView.goBack(); else super.onBackPressed();
    }

    /** Bridge agar halaman web bisa menyalakan backend via Termux RUN_COMMAND. */
    private class BackendBridge {
        @JavascriptInterface
        public boolean isTermuxInstalled() {
            try {
                getPackageManager().getPackageInfo(TERMUX_PKG, 0);
                return true;
            } catch (PackageManager.NameNotFoundException e) {
                return false;
            }
        }

        @JavascriptInterface
        public String backendCommand() {
            return "bash ~/crypto-strategy-app/apps/backend/server.sh start";
        }

        @JavascriptInterface
        public String startBackend(String action) {
            if (!"restart".equals(action)) action = "start";
            try {
                Intent i = new Intent("com.termux.RUN_COMMAND");
                i.setPackage(TERMUX_PKG);
                i.putExtra("com.termux.RUN_COMMAND_PATH", "/data/data/com.termux/files/usr/bin/bash");
                i.putExtra("com.termux.RUN_COMMAND_ARGUMENTS",
                        new String[]{BACKEND_DIR + "/server.sh", action});
                i.putExtra("com.termux.RUN_COMMAND_WORKDIR", BACKEND_DIR);
                i.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true);
                i.putExtra("com.termux.RUN_COMMAND_SESSION_ACTION", "1");
                sendBroadcast(i);
                return "ok";
            } catch (Exception e) {
                return "error: " + e.getMessage();
            }
        }

        @JavascriptInterface
        public boolean openTermux() {
            try {
                Intent li = getPackageManager().getLaunchIntentForPackage(TERMUX_PKG);
                if (li == null) return false;
                startActivity(li);
                return true;
            } catch (Exception e) {
                return false;
            }
        }
    }
}
