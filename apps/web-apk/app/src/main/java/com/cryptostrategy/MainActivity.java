package com.cryptostrategy;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.NotificationCompat;

public class MainActivity extends AppCompatActivity {
    private static final String TERMUX_PKG = "com.termux";
    private static final String BACKEND_DIR = "/data/data/com.termux/files/home/crypto-strategy-app/apps/backend";
    private static final String CHANNEL_ID = "backend_control";
    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        createNotificationChannel();

        webView = findViewById(R.id.webview);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setAllowFileAccessFromFileURLs(true);
        settings.setAllowUniversalAccessFromFileURLs(true);
        settings.setMixedContentMode(android.webkit.WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        settings.setMediaPlaybackRequiresUserGesture(false);
        webView.setWebViewClient(new android.webkit.WebViewClient());
        webView.setWebChromeClient(new android.webkit.WebChromeClient() {
            @Override
            public boolean onJsAlert(WebView view, String url, String message, android.webkit.JsResult result) {
                new androidx.appcompat.app.AlertDialog.Builder(MainActivity.this)
                    .setTitle("Crypto Strategy")
                    .setMessage(message)
                    .setPositiveButton(android.R.string.ok, (d, w) -> result.confirm())
                    .setCancelable(false)
                    .show();
                return true;
            }

            @Override
            public boolean onJsConfirm(WebView view, String url, String message, android.webkit.JsResult result) {
                new androidx.appcompat.app.AlertDialog.Builder(MainActivity.this)
                    .setTitle("Konfirmasi")
                    .setMessage(message)
                    .setPositiveButton(android.R.string.ok, (d, w) -> result.confirm())
                    .setNegativeButton(android.R.string.cancel, (d, w) -> result.cancel())
                    .setCancelable(false)
                    .show();
                return true;
            }
        });
        webView.addJavascriptInterface(new BackendBridge(), "AndroidBackend");
        webView.loadUrl("file:///android_asset/webapp/index.html");
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) webView.goBack(); else super.onBackPressed();
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel ch = new NotificationChannel(CHANNEL_ID, "Backend Control", NotificationManager.IMPORTANCE_LOW);
            ch.setDescription("Start/restart backend server");
            ((NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE)).createNotificationChannel(ch);
        }
    }

    private class BackendBridge {
        @JavascriptInterface
        public String getDeviceId() {
            try {
                String androidId = android.provider.Settings.Secure.getString(getContentResolver(), android.provider.Settings.Secure.ANDROID_ID);
                if (androidId != null && !androidId.isEmpty()) {
                    return "android-" + androidId;
                }
            } catch (Exception ignored) {}
            return "android-device";
        }

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
            String cmd = "bash " + BACKEND_DIR + "/server.sh " + action;

            // Method 1: Try Termux:Tasker RUN_COMMAND (if installed)
            try {
                Intent tasker = new Intent("com.twofortyfouram.intent.ACTION_FIRE_SETTING");
                tasker.setPackage("com.joaomgcd.tasker");
                tasker.putExtra("com.twofortyfouram.intent.EXTRA_INTENT", new Intent("com.termux.RUN_COMMAND")
                    .setPackage(TERMUX_PKG)
                    .putExtra("com.termux.RUN_COMMAND_PATH", "/data/data/com.termux/files/usr/bin/bash")
                    .putExtra("com.termux.RUN_COMMAND_ARGUMENTS", new String[]{BACKEND_DIR + "/server.sh", action})
                    .putExtra("com.termux.RUN_COMMAND_WORKDIR", BACKEND_DIR)
                    .putExtra("com.termux.RUN_COMMAND_BACKGROUND", true));
                sendBroadcast(tasker);
            } catch (Exception ignored) {}

            // Method 2: Open Termux with RUN_COMMAND intent (works on some devices)
            try {
                Intent i = new Intent("com.termux.RUN_COMMAND");
                i.setPackage(TERMUX_PKG);
                i.putExtra("com.termux.RUN_COMMAND_PATH", "/data/data/com.termux/files/usr/bin/bash");
                i.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", new String[]{BACKEND_DIR + "/server.sh", action});
                i.putExtra("com.termux.RUN_COMMAND_WORKDIR", BACKEND_DIR);
                i.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true);
                i.putExtra("com.termux.RUN_COMMAND_SESSION_ACTION", "1");
                sendBroadcast(i);
            } catch (Exception ignored) {}

            // Method 3: Launch Termux app (user runs command manually)
            // Always do this as fallback
            showBackendNotification(cmd, action);
            try {
                Intent li = getPackageManager().getLaunchIntentForPackage(TERMUX_PKG);
                if (li != null) {
                    li.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    startActivity(li);
                }
            } catch (Exception ignored) {}

            return "ok";
        }

        @JavascriptInterface
        public boolean openTermux() {
            try {
                Intent li = getPackageManager().getLaunchIntentForPackage(TERMUX_PKG);
                if (li == null) return false;
                li.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(li);
                return true;
            } catch (Exception e) {
                return false;
            }
        }

        @JavascriptInterface
        public void copyCommand(String cmd) {
            ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            if (cm != null) {
                cm.setPrimaryClip(ClipData.newPlainText("backend_cmd", cmd));
            }
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    Toast.makeText(MainActivity.this, "Command copied!", Toast.LENGTH_SHORT).show();
                }
            });
        }
    }

    private void showBackendNotification(String cmd, String action) {
        // Copy command to clipboard
        ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        if (cm != null) {
            cm.setPrimaryClip(ClipData.newPlainText("backend_cmd", cmd));
        }

        // Open Termux intent for notification tap
        Intent openTermux = getPackageManager().getLaunchIntentForPackage(TERMUX_PKG);
        if (openTermux != null) openTermux.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        PendingIntent pi = PendingIntent.getActivity(this, 0, openTermux, PendingIntent.FLAG_IMMUTABLE);

        Notification n = new NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_send)
            .setContentTitle("Backend " + action)
            .setContentText("Tap to open Termux, then paste & run:")
            .setStyle(new NotificationCompat.BigTextStyle()
                .bigText(cmd + "\n\n(Command copied to clipboard)"))
            .setContentIntent(pi)
            .setAutoCancel(true)
            .build();

        ((NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE)).notify(1001, n);
    }
}
