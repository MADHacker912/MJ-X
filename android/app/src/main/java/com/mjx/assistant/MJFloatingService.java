package com.mjx.assistant;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.graphics.PixelFormat;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.util.Log;
import android.view.Gravity;
import android.view.LayoutInflater;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

public class MJFloatingService extends Service {

    private static final String TAG = "MJFloatingService";
    private static final String CHANNEL_ID = "mjx_agent_channel";

    private WindowManager windowManager;
    private View overlayView;
    private View overlayPill;
    private View overlayExpandedMenu;
    private TextView overlayLabel;

    private boolean isMenuExpanded = false;
    private boolean isHiddenToEdge = false;

    private WindowManager.LayoutParams params;
    private OpenRouterClient openRouterClient;
    private VoiceEngine voiceEngine;
    private Handler mainHandler;

    @Override
    public void onCreate() {
        super.onCreate();
        mainHandler = new Handler(Looper.getMainLooper());
        openRouterClient = new OpenRouterClient(this);
        voiceEngine = new VoiceEngine(this);

        createNotificationChannel();
        startForeground(101, buildNotification());
        initFloatingHUD();
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "MJ-X Autonomous Agent",
                    NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("24/7 autonomous phone agent");
            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) manager.createNotificationChannel(channel);
        }
    }

    private Notification buildNotification() {
        Notification.Builder builder;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            builder = new Notification.Builder(this, CHANNEL_ID);
        } else {
            builder = new Notification.Builder(this);
        }
        return builder.setContentTitle("MJ-X Agent Active (24/7)")
                .setContentText("Autonomous phone control & voice listening online")
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .build();
    }

    private void initFloatingHUD() {
        windowManager = (WindowManager) getSystemService(WINDOW_SERVICE);

        LayoutInflater inflater = LayoutInflater.from(this);
        overlayView = inflater.inflate(R.layout.view_floating_hud, null);

        overlayPill = overlayView.findViewById(R.id.overlayPill);
        overlayExpandedMenu = overlayView.findViewById(R.id.overlayExpandedMenu);
        overlayLabel = overlayView.findViewById(R.id.overlayLabel);

        Button btnVoice = overlayView.findViewById(R.id.btnOverlayVoice);
        Button btnScan = overlayView.findViewById(R.id.btnOverlayScan);
        Button btnMute = overlayView.findViewById(R.id.btnOverlayMute);
        Button btnEnd = overlayView.findViewById(R.id.btnOverlayEnd);
        Button btnHide = overlayView.findViewById(R.id.btnOverlayHide);

        int layoutFlag = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O ?
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY :
                WindowManager.LayoutParams.TYPE_PHONE;

        params = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.WRAP_CONTENT,
                layoutFlag,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
                PixelFormat.TRANSLUCENT
        );

        params.gravity = Gravity.TOP | Gravity.START;
        params.x = 30;
        params.y = 250;

        // Pill touch listener: drag to reposition or tap to expand
        overlayPill.setOnTouchListener(new View.OnTouchListener() {
            private int initialX, initialY;
            private float initialTouchX, initialTouchY;

            @Override
            public boolean onTouch(View v, MotionEvent event) {
                switch (event.getAction()) {
                    case MotionEvent.ACTION_DOWN:
                        initialX = params.x;
                        initialY = params.y;
                        initialTouchX = event.getRawX();
                        initialTouchY = event.getRawY();
                        return true;

                    case MotionEvent.ACTION_MOVE:
                        params.x = initialX + (int) (event.getRawX() - initialTouchX);
                        params.y = initialY + (int) (event.getRawY() - initialTouchY);
                        windowManager.updateViewLayout(overlayView, params);
                        return true;

                    case MotionEvent.ACTION_UP:
                        if (Math.abs(event.getRawX() - initialTouchX) < 15 && Math.abs(event.getRawY() - initialTouchY) < 15) {
                            toggleExpandedMenu();
                        }
                        return true;
                }
                return false;
            }
        });

        // Expanded menu actions
        btnVoice.setOnClickListener(v -> triggerVoiceCommand());
        btnScan.setOnClickListener(v -> scanScreenAndAnalyze());
        btnMute.setOnClickListener(v -> {
            voiceEngine.stopSpeaking();
            Toast.makeText(this, "MJ-X Voice Muted", Toast.LENGTH_SHORT).show();
            collapseMenu();
        });
        btnEnd.setOnClickListener(v -> {
            voiceEngine.stopSpeaking();
            Toast.makeText(this, "Task Cancelled", Toast.LENGTH_SHORT).show();
            collapseMenu();
        });
        btnHide.setOnClickListener(v -> hideToEdge());

        windowManager.addView(overlayView, params);
    }

    private void toggleExpandedMenu() {
        if (isHiddenToEdge) {
            // Restore from edge
            params.x = 40;
            overlayLabel.setVisibility(View.VISIBLE);
            windowManager.updateViewLayout(overlayView, params);
            isHiddenToEdge = false;
            return;
        }

        isMenuExpanded = !isMenuExpanded;
        overlayExpandedMenu.setVisibility(isMenuExpanded ? View.VISIBLE : View.GONE);
    }

    private void collapseMenu() {
        isMenuExpanded = false;
        overlayExpandedMenu.setVisibility(View.GONE);
    }

    private void hideToEdge() {
        collapseMenu();
        isHiddenToEdge = true;
        params.x = -60; // Push mostly offscreen
        overlayLabel.setVisibility(View.GONE);
        windowManager.updateViewLayout(overlayView, params);
        Toast.makeText(this, "Pill hidden to edge. Tap to expand.", Toast.LENGTH_SHORT).show();
    }

    private void triggerVoiceCommand() {
        collapseMenu();
        overlayLabel.setText(" Listening...");
        voiceEngine.startListening(new VoiceEngine.VoiceCallback() {
            @Override
            public void onSpeechRecognized(String text) {
                overlayLabel.setText(" Thinking...");
                processUserCommand(text);
            }

            @Override public void onListeningStarted() {}
            @Override
            public void onListeningStopped() {
                overlayLabel.setText(" MJ-X Agent");
            }

            @Override
            public void onError(String error) {
                overlayLabel.setText(" MJ-X Agent");
                Toast.makeText(MJFloatingService.this, "Voice error: " + error, Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void scanScreenAndAnalyze() {
        collapseMenu();
        MJAccessibilityService service = MJAccessibilityService.getInstance();
        if (service != null) {
            String hierarchy = service.getScreenHierarchyJson();
            overlayLabel.setText(" Analyzing Screen...");
            processUserCommand("Look at the current screen elements and summarize what is happening:\n" + hierarchy);
        } else {
            Toast.makeText(this, "Enable Accessibility in Settings first", Toast.LENGTH_SHORT).show();
        }
    }

    private void processUserCommand(String prompt) {
        String screenCtx = "";
        MJAccessibilityService service = MJAccessibilityService.getInstance();
        if (service != null) {
            screenCtx = service.getScreenHierarchyJson();
        }

        openRouterClient.sendPrompt(prompt, screenCtx, new OpenRouterClient.AgentCallback() {
            @Override
            public void onResponse(String textResponse, JSONObject toolCall) {
                overlayLabel.setText(" MJ-X Agent");
                voiceEngine.speak(textResponse);
                Toast.makeText(MJFloatingService.this, textResponse, Toast.LENGTH_LONG).show();

                if (toolCall != null && service != null) {
                    mainHandler.postDelayed(() -> {
                        String res = service.executeTool(toolCall);
                        Log.i(TAG, "Tool executed on phone: " + res);
                    }, 500);
                }
            }

            @Override
            public void onError(String error) {
                overlayLabel.setText(" Error");
                Toast.makeText(MJFloatingService.this, error, Toast.LENGTH_LONG).show();
            }
        });
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        if (voiceEngine != null) voiceEngine.destroy();
        if (overlayView != null && windowManager != null) {
            windowManager.removeView(overlayView);
        }
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
