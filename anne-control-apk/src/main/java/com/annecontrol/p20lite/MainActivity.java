package com.annecontrol.p20lite;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ContentResolver;
import android.content.Intent;
import android.database.Cursor;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.DocumentsContract;
import android.provider.OpenableColumns;
import android.util.Base64;
import android.view.View;
import android.view.Window;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

public class MainActivity extends Activity {

    private static final String JS_RESUME = "window.onAnneResume && window.onAnneResume();";
    private static final int REQUEST_THEME_FILE = 4101;
    private static final int REQUEST_THEME_FOLDER = 4102;
    private static final long MAX_THEME_BYTES = 100L * 1024L * 1024L;
    private static final long MAX_THEME_EXPANDED_BYTES = 120L * 1024L * 1024L;
    private static final int MAX_THEME_ENTRIES = 5000;
    private static final int MAX_PREVIEW_BYTES = 2 * 1024 * 1024;
    private static final int MAX_DESCRIPTION_BYTES = 64 * 1024;

    private WebView webView;
    private SystemBridge bridge;
    private Uri pendingThemeUri;
    private String pendingThemeName;
    private volatile String lastThemeInspectionJson = "{}";
    private volatile String lastThemeImportStatus = "not_started";

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
        bridge = new SystemBridge(this, webView);
        webView.addJavascriptInterface(bridge, "AnneNative");

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

    /** Select and inspect a user-provided .hwt file before offering import. */
    public void beginHuaweiThemeImport() {
        runOnUiThread(new Runnable() {
            @Override public void run() {
                pendingThemeUri = null;
                pendingThemeName = null;
                lastThemeImportStatus = "selection_started";
                Intent pick = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                pick.addCategory(Intent.CATEGORY_OPENABLE);
                // Providers disagree about the MIME type used for .hwt files.
                pick.setType("*/*");
                try {
                    startActivityForResult(pick, REQUEST_THEME_FILE);
                } catch (Exception e) {
                    showThemeError("No file picker is available on this device.");
                }
            }
        });
    }

    /** Called only after the preview is shown and the user taps Import. */
    public void beginThemeFolderSelection() {
        runOnUiThread(new Runnable() {
            @Override public void run() {
                if (pendingThemeUri == null) {
                    showThemeError("Choose and preview a theme file first.");
                    return;
                }
                Intent folder = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
                try {
                    startActivityForResult(folder, REQUEST_THEME_FOLDER);
                } catch (Exception e) {
                    showThemeError("No folder picker is available on this device.");
                }
            }
        });
    }

    private void showThemeError(String message) {
        Toast.makeText(this, message, Toast.LENGTH_LONG).show();
        if (webView != null) {
            webView.evaluateJavascript("window.onThemeImportError && window.onThemeImportError(" +
                    org.json.JSONObject.quote(message) + ");", null);
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_THEME_FILE) {
            if (resultCode != RESULT_OK || data == null || data.getData() == null) {
                lastThemeImportStatus = "file_selection_cancelled";
                return;
            }
            final Uri selected = data.getData();
            final String name = queryDisplayName(selected);
            if (name == null || !name.toLowerCase(Locale.ROOT).endsWith(".hwt")) {
                lastThemeImportStatus = "invalid_file_type";
                showThemeError("Choose a Huawei theme file ending in .hwt.");
                return;
            }
            pendingThemeUri = selected;
            pendingThemeName = name;
            int flags = data.getFlags() & (Intent.FLAG_GRANT_READ_URI_PERMISSION
                    | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            try {
                getContentResolver().takePersistableUriPermission(selected,
                        flags & (Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION));
            } catch (Exception ignored) {
                // The picker may grant only temporary access; this session can still inspect/import it.
            }
            Toast.makeText(this, "Checking theme package…", Toast.LENGTH_SHORT).show();
            new Thread(new Runnable() {
                @Override public void run() {
                    final org.json.JSONObject result = inspectThemeFile(selected, name);
                    try {
                        lastThemeInspectionJson = result.toString();
                        lastThemeImportStatus = result.optBoolean("ok", false) ? "preview_ready" : "inspection_failed";
                    } catch (Exception ignored) {
                        lastThemeImportStatus = "inspection_failed";
                    }
                    runOnUiThread(new Runnable() {
                        @Override public void run() {
                            if (webView != null) {
                                webView.evaluateJavascript("window.onThemePreview && window.onThemePreview(" +
                                        org.json.JSONObject.quote(result.toString()) + ");", null);
                            }
                        }
                    });
                }
            }, "anne-theme-inspector").start();
            return;
        }

        if (requestCode == REQUEST_THEME_FOLDER) {
            if (resultCode != RESULT_OK || data == null || data.getData() == null
                    || pendingThemeUri == null || pendingThemeName == null) {
                lastThemeImportStatus = "folder_selection_cancelled";
                return;
            }
            final Uri treeUri = data.getData();
            if (!isHuaweiThemesFolder(treeUri)) {
                lastThemeImportStatus = "wrong_folder_selected";
                showThemeError("For safety, select Huawei/Themes (or HWThemes on some builds).");
                return;
            }

            final Uri sourceUri = pendingThemeUri;
            final String fileName = pendingThemeName;
            int flags = data.getFlags() & (Intent.FLAG_GRANT_READ_URI_PERMISSION
                    | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            try {
                getContentResolver().takePersistableUriPermission(treeUri, flags);
            } catch (Exception ignored) {
                // Some document providers grant access only for this activity result.
            }
            lastThemeImportStatus = "copying_to_theme_folder";
            Toast.makeText(this, "Importing theme…", Toast.LENGTH_SHORT).show();
            new Thread(new Runnable() {
                @Override public void run() {
                    try {
                        copyThemeIntoFolder(sourceUri, treeUri, fileName);
                        lastThemeImportStatus = "copied_to_theme_folder";
                        runOnUiThread(new Runnable() {
                            @Override public void run() {
                                Toast.makeText(MainActivity.this,
                                        "Theme copied. Open Huawei Themes and tap Apply when you are ready.",
                                        Toast.LENGTH_LONG).show();
                                if (webView != null) {
                                    webView.evaluateJavascript("window.onThemeImportComplete && window.onThemeImportComplete();", null);
                                }
                                openHuaweiThemes();
                            }
                        });
                    } catch (final Exception e) {
                        lastThemeImportStatus = "copy_failed";
                        runOnUiThread(new Runnable() {
                            @Override public void run() { showThemeError("Theme import failed: " + safeMessage(e)); }
                        });
                    }
                }
            }, "anne-theme-import").start();
        }
    }

    private org.json.JSONObject inspectThemeFile(Uri uri, String fileName) {
        org.json.JSONObject result = new org.json.JSONObject();
        try {
            long fileBytes = queryFileSize(uri);
            if (fileBytes > MAX_THEME_BYTES) throw new IllegalArgumentException("Theme files larger than 100 MB are not supported.");
            InputStream raw = getContentResolver().openInputStream(uri);
            if (raw == null) throw new IllegalStateException("Could not read the selected file.");
            ZipInputStream zip = new ZipInputStream(raw);
            Set<String> paths = new HashSet<String>();
            byte[] description = null;
            byte[] bestPreview = null;
            String bestPreviewName = null;
            int bestPreviewRank = Integer.MAX_VALUE;
            long expanded = 0L;
            int count = 0;
            byte[] buffer = new byte[16 * 1024];
            try {
                ZipEntry entry;
                while ((entry = zip.getNextEntry()) != null) {
                    if (++count > MAX_THEME_ENTRIES) throw new IllegalArgumentException("Theme has too many archive entries.");
                    String path = entry.getName() == null ? "" : entry.getName().replace('\\', '/');
                    while (path.startsWith("./")) path = path.substring(2);
                    if (path.startsWith("/") || path.contains("../")) {
                        throw new IllegalArgumentException("Theme contains an unsafe archive path.");
                    }
                    String lower = path.toLowerCase(Locale.ROOT);
                    if (!entry.isDirectory()) paths.add(lower);
                    boolean isDescription = "description.xml".equals(lower);
                    int previewRank = previewRank(lower);
                    boolean capture = isDescription || previewRank >= 0;
                    int captureLimit = isDescription ? MAX_DESCRIPTION_BYTES : MAX_PREVIEW_BYTES;
                    ByteArrayOutputStream captureBytes = capture ? new ByteArrayOutputStream() : null;
                    long entryExpanded = 0L;
                    boolean captureOverflow = false;
                    int read;
                    while ((read = zip.read(buffer)) != -1) {
                        expanded += read;
                        entryExpanded += read;
                        if (expanded > MAX_THEME_EXPANDED_BYTES) throw new IllegalArgumentException("Theme expands beyond the 120 MB safety limit.");
                        if (capture && !captureOverflow) {
                            if (entryExpanded <= captureLimit) captureBytes.write(buffer, 0, read);
                            else captureOverflow = true;
                        }
                    }
                    if (capture && !captureOverflow) {
                        byte[] bytes = captureBytes.toByteArray();
                        if (isDescription) description = bytes;
                        else if (previewRank < bestPreviewRank && isSupportedImage(bytes)) {
                            bestPreview = bytes;
                            bestPreviewName = path;
                            bestPreviewRank = previewRank;
                        }
                    }
                    zip.closeEntry();
                }
            } finally {
                zip.close();
            }
            if (count == 0) throw new IllegalArgumentException("The selected file is not a readable ZIP/HWT archive.");

            String xml = description == null ? "" : new String(description, StandardCharsets.UTF_8);
            org.json.JSONObject modules = new org.json.JSONObject();
            modules.put("description", description != null);
            modules.put("wallpaper", hasPath(paths, "wallpaper/"));
            modules.put("icons", paths.contains("icons"));
            modules.put("launcher", paths.contains("com.huawei.android.launcher"));
            modules.put("systemUi", paths.contains("com.android.systemui"));
            modules.put("settings", paths.contains("com.android.settings"));
            modules.put("preview", bestPreview != null);

            org.json.JSONArray checks = new org.json.JSONArray();
            checks.put(check("HWT/ZIP readable", true, count + " entries checked"));
            checks.put(check("Theme metadata", description != null, description != null ? "description.xml found" : "No description.xml found"));
            checks.put(check("Preview artwork", bestPreview != null, bestPreview != null ? bestPreviewName : "No supported preview image found"));
            checks.put(check("Launcher icons", paths.contains("icons") || paths.contains("icons/icons"),
                    paths.contains("icons") || paths.contains("icons/icons") ? "Icon package present" : "No icon package found"));
            boolean target = "HUAWEI".equalsIgnoreCase(Build.MANUFACTURER)
                    && Build.VERSION.SDK_INT == 28
                    && Build.MODEL != null && Build.MODEL.toUpperCase(Locale.ROOT).contains("ANE-LX1");
            checks.put(check("Device target", target,
                    target ? "ANE-LX1 / Android 9 target detected" : "Not the app's validated target; compatibility is unknown"));

            result.put("ok", true);
            result.put("fileName", fileName);
            result.put("fileBytes", fileBytes);
            result.put("expandedBytes", expanded);
            result.put("entryCount", count);
            result.put("themeName", xmlTag(xml, "title", "Theme name not present"));
            result.put("version", xmlTag(xml, "version", "Unknown"));
            result.put("screen", xmlTag(xml, "screen", "Unknown"));
            result.put("font", xmlTag(xml, "font", "Default/unspecified"));
            result.put("modules", modules);
            result.put("checks", checks);
            result.put("deviceSupported", target);
            result.put("previewEntry", bestPreviewName == null ? "" : bestPreviewName);
            result.put("previewMime", bestPreview != null && isPng(bestPreview) ? "image/png" : "image/jpeg");
            result.put("previewImageBase64", bestPreview == null ? "" : Base64.encodeToString(bestPreview, Base64.NO_WRAP));
            result.put("notice", "Archive checks are structural only; Huawei Themes must confirm actual compatibility. Nothing is applied during preview.");
        } catch (Exception e) {
            try {
                result.put("ok", false);
                result.put("fileName", fileName == null ? "" : fileName);
                result.put("error", safeMessage(e));
                result.put("checks", new org.json.JSONArray().put(check("Theme inspection", false, safeMessage(e))));
            } catch (Exception ignored) {
            }
        }
        return result;
    }

    private static org.json.JSONObject check(String name, boolean ok, String detail) throws org.json.JSONException {
        return new org.json.JSONObject().put("name", name).put("ok", ok).put("detail", detail);
    }

    private static boolean hasPath(Set<String> paths, String prefix) {
        for (String path : paths) if (path.startsWith(prefix)) return true;
        return false;
    }

    private static int previewRank(String path) {
        if ("preview/cover.jpg".equals(path) || "preview/cover.png".equals(path)) return 0;
        if ("preview/preview_wallpaper_0.jpg".equals(path) || "preview/preview_wallpaper_0.png".equals(path)) return 1;
        if ("preview/preview_unlock_0.jpg".equals(path) || "preview/preview_unlock_0.png".equals(path)) return 2;
        if ("preview/preview_icons_0.jpg".equals(path) || "preview/preview_icons_0.png".equals(path)) return 3;
        if (path.startsWith("preview/") && (path.endsWith(".jpg") || path.endsWith(".jpeg") || path.endsWith(".png"))) return 10;
        if ((path.equals("wallpaper/home_wallpaper_0.jpg") || path.equals("wallpaper/home_wallpaper_0.png"))) return 20;
        return -1;
    }

    private static boolean isSupportedImage(byte[] data) {
        return isPng(data) || (data != null && data.length > 2 && (data[0] & 255) == 255 && (data[1] & 255) == 216);
    }

    private static boolean isPng(byte[] data) {
        return data != null && data.length >= 8 && data[0] == (byte)137 && data[1] == 80
                && data[2] == 78 && data[3] == 71 && data[4] == 13 && data[5] == 10
                && data[6] == 26 && data[7] == 10;
    }

    private static String xmlTag(String xml, String tag, String fallback) {
        if (xml == null || xml.length() == 0) return fallback;
        Pattern pattern = Pattern.compile("<" + Pattern.quote(tag) + "\\s*>(.*?)</" + Pattern.quote(tag) + "\\s*>",
                Pattern.CASE_INSENSITIVE | Pattern.DOTALL);
        Matcher matcher = pattern.matcher(xml);
        if (!matcher.find()) return fallback;
        String value = matcher.group(1).replaceAll("<[^>]*>", "").trim();
        value = value.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">");
        return value.length() > 100 ? value.substring(0, 100) : value;
    }

    private long queryFileSize(Uri uri) {
        Cursor cursor = null;
        try {
            cursor = getContentResolver().query(uri, new String[]{OpenableColumns.SIZE}, null, null, null);
            if (cursor != null && cursor.moveToFirst()) {
                int index = cursor.getColumnIndex(OpenableColumns.SIZE);
                if (index >= 0 && !cursor.isNull(index)) return cursor.getLong(index);
            }
        } catch (Exception ignored) {
        } finally {
            if (cursor != null) cursor.close();
        }
        return -1L;
    }

    public String getLastThemeInspectionJson() {
        try {
            org.json.JSONObject report = new org.json.JSONObject(lastThemeInspectionJson);
            report.remove("previewImageBase64");
            report.remove("previewMime");
            report.put("importStatus", lastThemeImportStatus);
            return report.toString();
        } catch (Exception e) {
            return "{\"importStatus\":\"" + lastThemeImportStatus + "\"}";
        }
    }

    private void copyThemeIntoFolder(Uri source, Uri tree, String originalName) throws Exception {
        ContentResolver resolver = getContentResolver();
        Set<String> existing = new HashSet<String>();
        String treeId = DocumentsContract.getTreeDocumentId(tree);
        Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, treeId);
        Cursor cursor = null;
        try {
            cursor = resolver.query(children,
                    new String[]{DocumentsContract.Document.COLUMN_DISPLAY_NAME}, null, null, null);
            if (cursor != null) {
                int nameIndex = cursor.getColumnIndex(DocumentsContract.Document.COLUMN_DISPLAY_NAME);
                while (nameIndex >= 0 && cursor.moveToNext()) {
                    existing.add(cursor.getString(nameIndex));
                }
            }
        } finally {
            if (cursor != null) cursor.close();
        }

        String targetName = uniqueThemeName(originalName, existing);
        Uri parent = DocumentsContract.buildDocumentUriUsingTree(tree, treeId);
        Uri target = DocumentsContract.createDocument(resolver, parent,
                "application/octet-stream", targetName);
        if (target == null) throw new IllegalStateException("The selected folder did not accept the file.");

        InputStream in = null;
        OutputStream out = null;
        boolean complete = false;
        long copied = 0L;
        try {
            in = resolver.openInputStream(source);
            out = resolver.openOutputStream(target, "w");
            if (in == null || out == null) throw new IllegalStateException("Could not open the selected file.");
            byte[] buffer = new byte[32 * 1024];
            int count;
            while ((count = in.read(buffer)) != -1) {
                copied += count;
                if (copied > MAX_THEME_BYTES) {
                    throw new IllegalArgumentException("Theme files larger than 100 MB are not supported.");
                }
                out.write(buffer, 0, count);
            }
            out.flush();
            if (copied == 0L) throw new IllegalArgumentException("The selected theme file is empty.");
            complete = true;
        } finally {
            if (in != null) try { in.close(); } catch (Exception ignored) {}
            if (out != null) try { out.close(); } catch (Exception ignored) {}
            if (!complete) {
                try { DocumentsContract.deleteDocument(resolver, target); } catch (Exception ignored) {}
            }
        }
    }

    private String queryDisplayName(Uri uri) {
        Cursor cursor = null;
        try {
            cursor = getContentResolver().query(uri,
                    new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null);
            if (cursor != null && cursor.moveToFirst()) {
                int index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (index >= 0) return cursor.getString(index);
            }
        } catch (Exception ignored) {
        } finally {
            if (cursor != null) cursor.close();
        }
        return null;
    }

    private static boolean isHuaweiThemesFolder(Uri tree) {
        try {
            String documentId = DocumentsContract.getTreeDocumentId(tree);
            int volumeSeparator = documentId.indexOf(':');
            if (volumeSeparator < 0) return false;
            String relativePath = documentId.substring(volumeSeparator + 1).replace('\\', '/');
            while (relativePath.startsWith("/")) relativePath = relativePath.substring(1);
            return "Huawei/Themes".equalsIgnoreCase(relativePath)
                    || "HWThemes".equalsIgnoreCase(relativePath);
        } catch (Exception ignored) {
            return false;
        }
    }

    private static String uniqueThemeName(String name, Set<String> existing) {
        if (!existing.contains(name)) return name;
        String stem = name.substring(0, name.length() - 4);
        for (int i = 2; i < 10000; i++) {
            String candidate = stem + " (" + i + ").hwt";
            if (!existing.contains(candidate)) return candidate;
        }
        throw new IllegalStateException("Too many themes with the same file name.");
    }

    private void openHuaweiThemes() {
        String[] packages = {"com.huawei.android.thememanager", "com.android.thememanager"};
        for (String packageName : packages) {
            try {
                Intent launch = getPackageManager().getLaunchIntentForPackage(packageName);
                if (launch != null) {
                    startActivity(launch);
                    return;
                }
            } catch (Exception ignored) {
            }
        }
    }

    private static String safeMessage(Exception e) {
        String message = e.getMessage();
        return message == null || message.length() == 0 ? "could not access the selected file or folder" : message;
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
        if (bridge != null) {
            bridge.shutdown();   // stops the background cache scanner
            bridge = null;
        }
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
