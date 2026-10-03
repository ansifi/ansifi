package com.ansif.workspace;

import android.app.AlertDialog;
import android.content.Context;
import android.content.SharedPreferences;
import android.net.nsd.NsdManager;
import android.net.nsd.NsdServiceInfo;
import android.os.Bundle;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Toast;

import android.app.Activity;
import android.content.Intent;

import java.net.HttpURLConnection;
import java.net.InetAddress;
import java.net.URL;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

public class MainActivity extends Activity {
    private static final String PREFS = "ansif_workspace";
    private static final String KEY_URL = "hub_url";
    static final String PHONE_URL = "http://ansif-workspace.local:4040/";
    private static final String NSD_TYPE = "_ansif-workspace._tcp.";

    private WebView web;
    private SharedPreferences prefs;
    private NsdManager nsd;
    private final AtomicBoolean connected = new AtomicBoolean(false);

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        web = findViewById(R.id.web);
        Button hubUrlBtn = findViewById(R.id.hub_url_btn);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, true);

        web.setWebChromeClient(new WebChromeClient());
        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request == null || request.isForMainFrame()) {
                    connected.set(false);
                    view.loadDataWithBaseURL("about:blank", failHtml(), "text/html", "UTF-8", null);
                }
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (request == null || request.getUrl() == null) {
                    return false;
                }
                String host = request.getUrl().getHost();
                if (host == null) {
                    return false;
                }
                if (host.equals("127.0.0.1") || host.equals("localhost")
                        || host.equals("ansif-workspace.local")
                        || host.equals("ans.local")
                        || host.startsWith("192.168.")) {
                    return false;
                }
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, request.getUrl()));
                } catch (Exception ignored) {
                }
                return true;
            }
        });

        hubUrlBtn.setOnClickListener(v -> promptUrl());
        web.loadDataWithBaseURL("about:blank", lookingHtml(), "text/html", "UTF-8", null);
        new Thread(this::findDesktop).start();
        startNsd();
    }

    private List<String> candidates() {
        LinkedHashSet<String> urls = new LinkedHashSet<>();
        String saved = prefs.getString(KEY_URL, "");
        if (saved != null && !saved.trim().isEmpty()) {
            urls.add(normalize(saved));
        }
        urls.add(PHONE_URL);
        urls.add("http://ans.local:4040/");
        urls.add(getString(R.string.default_hub_url));
        return new ArrayList<>(urls);
    }

    private void findDesktop() {
        for (String url : candidates()) {
            if (reachable(url)) {
                openHub(url);
                return;
            }
        }
        runOnUiThread(() -> {
            if (!connected.get()) {
                web.loadDataWithBaseURL("about:blank", failHtml(), "text/html", "UTF-8", null);
            }
        });
    }

    private String originOf(String url) {
        String u = normalize(url);
        int appAt = u.indexOf("/app/");
        if (appAt > "http://x".length()) {
            u = u.substring(0, appAt + 1);
        }
        return u;
    }

    private boolean reachable(String base) {
        HttpURLConnection conn = null;
        try {
            URL url = new URL(originOf(base) + "auth/");
            conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(1800);
            conn.setReadTimeout(1800);
            conn.setInstanceFollowRedirects(false);
            conn.setRequestMethod("GET");
            int code = conn.getResponseCode();
            return code >= 200 && code < 500;
        } catch (Exception e) {
            return false;
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    private void openHub(String url) {
        if (!connected.compareAndSet(false, true)) {
            return;
        }
        final String origin = originOf(url);
        prefs.edit().putString(KEY_URL, origin).apply();
        runOnUiThread(() -> web.loadUrl(origin + "app/"));
    }

    private void startNsd() {
        nsd = (NsdManager) getSystemService(Context.NSD_SERVICE);
        if (nsd == null) {
            return;
        }
        nsd.discoverServices(NSD_TYPE, NsdManager.PROTOCOL_DNS_SD, new NsdManager.DiscoveryListener() {
            @Override
            public void onStartDiscoveryFailed(String serviceType, int errorCode) {}

            @Override
            public void onStopDiscoveryFailed(String serviceType, int errorCode) {}

            @Override
            public void onDiscoveryStarted(String serviceType) {}

            @Override
            public void onDiscoveryStopped(String serviceType) {}

            @Override
            public void onServiceLost(NsdServiceInfo serviceInfo) {}

            @Override
            public void onServiceFound(NsdServiceInfo serviceInfo) {
                if (serviceInfo == null || connected.get()) {
                    return;
                }
                nsd.resolveService(serviceInfo, new NsdManager.ResolveListener() {
                    @Override
                    public void onResolveFailed(NsdServiceInfo info, int errorCode) {}

                    @Override
                    public void onServiceResolved(NsdServiceInfo info) {
                        if (info == null || connected.get()) {
                            return;
                        }
                        InetAddress host = info.getHost();
                        int port = info.getPort() > 0 ? info.getPort() : 4040;
                        if (host == null) {
                            return;
                        }
                        openHub("http://" + host.getHostAddress() + ":" + port + "/");
                    }
                });
            }
        });
    }

    private String currentUrl() {
        String url = prefs.getString(KEY_URL, PHONE_URL);
        if (url == null || url.trim().isEmpty()) {
            url = PHONE_URL;
        }
        return normalize(url);
    }

    private static String normalize(String url) {
        String u = url == null ? "" : url.trim();
        if (u.isEmpty()) {
            return PHONE_URL;
        }
        if (!u.endsWith("/")) {
            u = u + "/";
        }
        return u;
    }

    private void promptUrl() {
        final EditText input = new EditText(this);
        input.setText(currentUrl());
        input.setHint(PHONE_URL);
        input.setSingleLine(true);
        input.setTextColor(0xFFE8EDF4);
        input.setHintTextColor(0xFF8B9AAF);
        input.setBackgroundColor(0xFF151C27);
        input.setPadding(32, 24, 32, 24);

        new AlertDialog.Builder(this)
                .setTitle("Hub URL")
                .setMessage("Leave as " + PHONE_URL + " while the desktop app is running on the same Wi-Fi.")
                .setView(input)
                .setPositiveButton("Open", (d, w) -> {
                    String url = input.getText().toString().trim();
                    if (url.isEmpty()) {
                        Toast.makeText(this, "URL is empty", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    connected.set(false);
                    openHub(url);
                })
                .setNeutralButton("Find desktop", (d, w) -> {
                    connected.set(false);
                    web.loadDataWithBaseURL("about:blank", lookingHtml(), "text/html", "UTF-8", null);
                    new Thread(this::findDesktop).start();
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    private String lookingHtml() {
        return page("Looking for desktop…",
                "<p>Trying <code>" + PHONE_URL + "</code></p>"
                + "<p>Keep the Ansif Workspace desktop app open on this Wi-Fi.</p>");
    }

    private String failHtml() {
        return page("Hub not reachable",
                "<p>Tried <code>" + currentUrl().replace("<", "") + "</code></p>"
                + "<p>Open the <b>A</b> desktop app on the PC, same Wi-Fi, then tap <b>Hub URL → Find desktop</b>.</p>"
                + "<p>Phone URL: <code>" + PHONE_URL + "</code></p>");
    }

    private static String page(String title, String body) {
        return "<!doctype html><html><head><meta charset='utf-8'>"
                + "<meta name='viewport' content='width=device-width, initial-scale=1'>"
                + "<style>body{font-family:sans-serif;background:#0c1118;color:#e8edf4;padding:24px;line-height:1.45}"
                + "code{color:#3dd6c7} p{color:#8b9aaf}</style></head><body>"
                + "<h2>" + title + "</h2>" + body + "</body></html>";
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) {
            web.goBack();
            return;
        }
        super.onBackPressed();
    }
}
