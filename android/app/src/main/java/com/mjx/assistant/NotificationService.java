package com.mjx.assistant;

import android.app.Notification;
import android.os.Bundle;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;
import android.util.Log;

import java.util.LinkedList;
import java.util.List;

public class NotificationService extends NotificationListenerService {

    private static final String TAG = "MJNotificationService";
    private static final LinkedList<String> sRecentNotifications = new LinkedList<>();

    public static synchronized List<String> getRecentNotifications() {
        return new LinkedList<>(sRecentNotifications);
    }

    public static synchronized void clearNotifications() {
        sRecentNotifications.clear();
    }

    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        if (sbn == null || sbn.getNotification() == null) return;

        Notification notif = sbn.getNotification();
        Bundle extras = notif.extras;
        if (extras == null) return;

        String pkg = sbn.getPackageName();
        CharSequence title = extras.getCharSequence(Notification.EXTRA_TITLE);
        CharSequence text = extras.getCharSequence(Notification.EXTRA_TEXT);

        if (title != null && text != null) {
            String record = "[" + friendlyAppName(pkg) + "] " + title + ": " + text;
            Log.i(TAG, "Captured notification: " + record);

            synchronized (NotificationService.class) {
                if (sRecentNotifications.size() > 30) {
                    sRecentNotifications.removeFirst();
                }
                sRecentNotifications.add(record);
            }
        }
    }

    private String friendlyAppName(String pkg) {
        if (pkg.contains("whatsapp")) return "WhatsApp";
        if (pkg.contains("dialer") || pkg.contains("telecom") || pkg.contains("incall")) return "Phone Call";
        if (pkg.contains("mms") || pkg.contains("messaging")) return "SMS";
        if (pkg.contains("instagram")) return "Instagram";
        if (pkg.contains("telegram")) return "Telegram";
        if (pkg.contains("youtube")) return "YouTube";
        return pkg;
    }

    @Override
    public void onNotificationRemoved(StatusBarNotification sbn) {}
}
