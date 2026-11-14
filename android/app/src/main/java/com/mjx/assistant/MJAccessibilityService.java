package com.mjx.assistant;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.content.ContentResolver;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.graphics.Path;
import android.graphics.Rect;
import android.net.Uri;
import android.os.Bundle;
import android.provider.ContactsContract;
import android.util.Log;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class MJAccessibilityService extends AccessibilityService {

    private static final String TAG = "MJAccessibilityService";
    private static MJAccessibilityService sInstance = null;

    private static final Map<String, String> APP_PACKAGE_MAP = new HashMap<>();
    static {
        APP_PACKAGE_MAP.put("whatsapp", "com.whatsapp");
        APP_PACKAGE_MAP.put("youtube", "com.google.android.youtube");
        APP_PACKAGE_MAP.put("chrome", "com.android.chrome");
        APP_PACKAGE_MAP.put("browser", "com.android.chrome");
        APP_PACKAGE_MAP.put("settings", "com.android.settings");
        APP_PACKAGE_MAP.put("camera", "com.android.camera");
        APP_PACKAGE_MAP.put("dialer", "com.google.android.dialer");
        APP_PACKAGE_MAP.put("phone", "com.google.android.dialer");
        APP_PACKAGE_MAP.put("contacts", "com.google.android.contacts");
        APP_PACKAGE_MAP.put("maps", "com.google.android.apps.maps");
        APP_PACKAGE_MAP.put("spotify", "com.spotify.music");
        APP_PACKAGE_MAP.put("calculator", "com.google.android.calculator");
        APP_PACKAGE_MAP.put("instagram", "com.instagram.android");
        APP_PACKAGE_MAP.put("telegram", "org.telegram.messenger");
    }

    public static MJAccessibilityService getInstance() {
        return sInstance;
    }

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        sInstance = this;
        Log.i(TAG, "MJ-X Autonomous Accessibility Service Connected!");
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {}

    @Override
    public void onInterrupt() {}

    @Override
    public void onDestroy() {
        super.onDestroy();
        sInstance = null;
    }

    /**
     * Launches any app by common name or package ID
     */
    public boolean launchApp(String appName) {
        String clean = appName.toLowerCase().trim().replace(" ", "");
        String pkg = APP_PACKAGE_MAP.get(clean);
        if (pkg == null) {
            pkg = findPackageByLabel(appName);
        }
        if (pkg == null) {
            pkg = clean;
        }

        try {
            Intent intent = getPackageManager().getLaunchIntentForPackage(pkg);
            if (intent != null) {
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(intent);
                return true;
            }
        } catch (Exception e) {
            Log.e(TAG, "Launch app failed: " + pkg, e);
        }
        return false;
    }

    private String findPackageByLabel(String label) {
        PackageManager pm = getPackageManager();
        List<android.content.pm.ApplicationInfo> apps = pm.getInstalledApplications(PackageManager.GET_META_DATA);
        for (android.content.pm.ApplicationInfo app : apps) {
            String appLabel = pm.getApplicationLabel(app).toString().toLowerCase();
            if (appLabel.contains(label.toLowerCase())) {
                return app.packageName;
            }
        }
        return null;
    }

    /**
     * Dials or places call to phone number or contact name
     */
    public boolean makeCall(String contactOrNumber) {
        String number = contactOrNumber.trim();
        if (!number.matches("^[+0-9\\-\\s]+$")) {
            // It's a name, lookup in contacts
            String found = lookupPhoneNumberByName(number);
            if (found != null) {
                number = found;
            }
        }

        try {
            Intent intent = new Intent(Intent.ACTION_CALL, Uri.parse("tel:" + number));
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
            return true;
        } catch (SecurityException se) {
            // Fallback to dialer if direct call permission not granted
            Intent dialIntent = new Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + number));
            dialIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(dialIntent);
            return true;
        } catch (Exception e) {
            Log.e(TAG, "Call failed: " + contactOrNumber, e);
            return false;
        }
    }

    private String lookupPhoneNumberByName(String name) {
        try {
            ContentResolver cr = getContentResolver();
            Cursor cursor = cr.query(
                    ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                    new String[]{ContactsContract.CommonDataKinds.Phone.NUMBER, ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME},
                    ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME + " LIKE ?",
                    new String[]{"%" + name + "%"},
                    null
            );
            if (cursor != null && cursor.moveToFirst()) {
                int colIdx = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER);
                String num = cursor.getString(colIdx);
                cursor.close();
                return num;
            }
        } catch (Exception ignored) {}
        return null;
    }

    /**
     * Opens WhatsApp conversation and types message
     */
    public boolean sendWhatsAppMessage(String contactOrNumber, String message) {
        launchApp("whatsapp");
        try {
            Thread.sleep(1200);
            // Click search
            findAndClickById("com.whatsapp:id/menuitem_search");
            Thread.sleep(500);
            inputText(contactOrNumber);
            Thread.sleep(1000);
            findAndClickByText(contactOrNumber);
            Thread.sleep(800);
            inputText(message);
            Thread.sleep(500);
            findAndClickById("com.whatsapp:id/send");
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    public boolean clickAt(float x, float y) {
        Path clickPath = new Path();
        clickPath.moveTo(x, y);
        GestureDescription.StrokeDescription stroke =
                new GestureDescription.StrokeDescription(clickPath, 0, 50);
        GestureDescription.Builder builder = new GestureDescription.Builder();
        builder.addStroke(stroke);
        return dispatchGesture(builder.build(), null, null);
    }

    public boolean swipe(float startX, float startY, float endX, float endY, long durationMs) {
        Path swipePath = new Path();
        swipePath.moveTo(startX, startY);
        swipePath.lineTo(endX, endY);
        GestureDescription.StrokeDescription stroke =
                new GestureDescription.StrokeDescription(swipePath, 0, durationMs);
        GestureDescription.Builder builder = new GestureDescription.Builder();
        builder.addStroke(stroke);
        return dispatchGesture(builder.build(), null, null);
    }

    public boolean findAndClickByText(String targetText) {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return false;

        List<AccessibilityNodeInfo> nodes = root.findAccessibilityNodeInfosByText(targetText);
        if (nodes != null && !nodes.isEmpty()) {
            for (AccessibilityNodeInfo node : nodes) {
                if (performClickOnNode(node)) return true;
            }
        }
        return false;
    }

    public boolean findAndClickById(String viewId) {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return false;

        List<AccessibilityNodeInfo> nodes = root.findAccessibilityNodeInfosByViewId(viewId);
        if (nodes != null && !nodes.isEmpty()) {
            for (AccessibilityNodeInfo node : nodes) {
                if (performClickOnNode(node)) return true;
            }
        }
        return false;
    }

    private boolean performClickOnNode(AccessibilityNodeInfo node) {
        AccessibilityNodeInfo current = node;
        while (current != null) {
            if (current.isClickable()) {
                return current.performAction(AccessibilityNodeInfo.ACTION_CLICK);
            }
            current = current.getParent();
        }
        Rect rect = new Rect();
        node.getBoundsInScreen(rect);
        if (rect.width() > 0 && rect.height() > 0) {
            return clickAt(rect.centerX(), rect.centerY());
        }
        return false;
    }

    public boolean inputText(String text) {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return false;

        AccessibilityNodeInfo focused = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
        if (focused != null && focused.isEditable()) {
            Bundle arguments = new Bundle();
            arguments.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text);
            return focused.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, arguments);
        }

        AccessibilityNodeInfo editable = findFirstEditableNode(root);
        if (editable != null) {
            Bundle arguments = new Bundle();
            arguments.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text);
            return editable.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, arguments);
        }
        return false;
    }

    private AccessibilityNodeInfo findFirstEditableNode(AccessibilityNodeInfo root) {
        if (root == null) return null;
        if (root.isEditable()) return root;
        for (int i = 0; i < root.getChildCount(); i++) {
            AccessibilityNodeInfo child = root.getChild(i);
            AccessibilityNodeInfo result = findFirstEditableNode(child);
            if (result != null) return result;
        }
        return null;
    }

    public boolean pressBack() { return performGlobalAction(GLOBAL_ACTION_BACK); }
    public boolean pressHome() { return performGlobalAction(GLOBAL_ACTION_HOME); }
    public boolean pressRecents() { return performGlobalAction(GLOBAL_ACTION_RECENTS); }
    public boolean openNotifications() { return performGlobalAction(GLOBAL_ACTION_NOTIFICATIONS); }

    public String getScreenHierarchyJson() {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return "{}";
        try {
            JSONObject json = nodeToJson(root);
            return json.toString();
        } catch (Exception e) {
            return "{\"error\": \"" + e.getMessage() + "\"}";
        }
    }

    private JSONObject nodeToJson(AccessibilityNodeInfo node) throws Exception {
        JSONObject obj = new JSONObject();
        if (node == null) return obj;

        CharSequence text = node.getText();
        CharSequence desc = node.getContentDescription();
        CharSequence id = node.getViewIdResourceName();
        if (text != null) obj.put("text", text.toString());
        if (desc != null) obj.put("desc", desc.toString());
        if (id != null) obj.put("id", id.toString());
        obj.put("clickable", node.isClickable());

        JSONArray children = new JSONArray();
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            if (child != null) children.put(nodeToJson(child));
        }
        if (children.length() > 0) obj.put("children", children);
        return obj;
    }

    /**
     * Executes parsed JSON tool call directly on device
     */
    public String executeTool(JSONObject tool) {
        try {
            String name = tool.optString("tool", tool.optString("action", ""));
            switch (name) {
                case "open_app":
                    boolean opened = launchApp(tool.optString("app", ""));
                    return opened ? "Launched app" : "Failed to launch app";

                case "make_call":
                    boolean called = makeCall(tool.optString("contact", ""));
                    return called ? "Calling contact" : "Call failed";

                case "send_whatsapp":
                    boolean sent = sendWhatsAppMessage(tool.optString("contact", ""), tool.optString("message", ""));
                    return sent ? "WhatsApp message dispatched" : "WhatsApp action failed";

                case "click_text":
                    boolean clicked = findAndClickByText(tool.optString("text", ""));
                    return clicked ? "Clicked text" : "Text element not found";

                case "type":
                    boolean typed = inputText(tool.optString("text", ""));
                    return typed ? "Entered text" : "No editable field found";

                case "navigate":
                    String nav = tool.optString("action", "");
                    if ("home".equals(nav)) return pressHome() ? "Home" : "Failed";
                    if ("back".equals(nav)) return pressBack() ? "Back" : "Failed";
                    if ("notifications".equals(nav)) return openNotifications() ? "Notifications" : "Failed";
                    return "Unknown navigation";

                default:
                    return "Unknown tool: " + name;
            }
        } catch (Exception e) {
            return "Tool error: " + e.getMessage();
        }
    }
}
