package com.mjx.assistant;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.View;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.util.List;

public class MainActivity extends Activity {

    private static final int PERMISSION_REQ_CODE = 1001;

    // Navigation Tabs
    private Button navTabFront, navTabSettings, navTabOverlay;
    private ScrollView tabFrontView, tabSettingsView, tabOverlayView;

    // Header & Credits
    private TextView creditText, modelNameText;

    // Front Tab UI
    private View avatarGlowOrb;
    private TextView agentStatusText, waveformText, transcriptLogText;
    private Button btnVoiceListen, btnReadNotifications, btnScanScreen;

    // Settings Tab UI
    private EditText apiKeyInput;
    private Button btnSaveApiKey, btnPermAccessibility, btnPermOverlay, btnPermNotifications;
    private Spinner modelSpinner;

    // Overlay Tab UI
    private Button btnToggleFloatingHUD;

    // Core engines
    private OpenRouterClient openRouterClient;
    private VoiceEngine voiceEngine;

    private final String[] MODELS = {
            "google/gemini-2.0-flash-exp:free",
            "anthropic/claude-3.5-sonnet",
            "meta-llama/llama-3.3-70b-instruct",
            "mistralai/mistral-small-24b-instruct-2501",
            "deepseek/deepseek-r1"
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        openRouterClient = new OpenRouterClient(this);
        voiceEngine = new VoiceEngine(this);

        initViews();
        setupTabs();
        setupSettings();
        setupFrontHUD();
        setupOverlayControls();
        requestRequiredPermissions();

        refreshCredits();
    }

    private void initViews() {
        navTabFront = findViewById(R.id.navTabFront);
        navTabSettings = findViewById(R.id.navTabSettings);
        navTabOverlay = findViewById(R.id.navTabOverlay);

        tabFrontView = findViewById(R.id.tabFrontView);
        tabSettingsView = findViewById(R.id.tabSettingsView);
        tabOverlayView = findViewById(R.id.tabOverlayView);

        creditText = findViewById(R.id.creditText);
        modelNameText = findViewById(R.id.modelNameText);

        avatarGlowOrb = findViewById(R.id.avatarGlowOrb);
        agentStatusText = findViewById(R.id.agentStatusText);
        waveformText = findViewById(R.id.waveformText);
        transcriptLogText = findViewById(R.id.transcriptLogText);

        btnVoiceListen = findViewById(R.id.btnVoiceListen);
        btnReadNotifications = findViewById(R.id.btnReadNotifications);
        btnScanScreen = findViewById(R.id.btnScanScreen);

        apiKeyInput = findViewById(R.id.apiKeyInput);
        btnSaveApiKey = findViewById(R.id.btnSaveApiKey);
        modelSpinner = findViewById(R.id.modelSpinner);

        btnPermAccessibility = findViewById(R.id.btnPermAccessibility);
        btnPermOverlay = findViewById(R.id.btnPermOverlay);
        btnPermNotifications = findViewById(R.id.btnPermNotifications);

        btnToggleFloatingHUD = findViewById(R.id.btnToggleFloatingHUD);
    }

    private void setupTabs() {
        navTabFront.setOnClickListener(v -> switchTab(0));
        navTabSettings.setOnClickListener(v -> switchTab(1));
        navTabOverlay.setOnClickListener(v -> switchTab(2));
    }

    private void switchTab(int tabIndex) {
        tabFrontView.setVisibility(tabIndex == 0 ? View.VISIBLE : View.GONE);
        tabSettingsView.setVisibility(tabIndex == 1 ? View.VISIBLE : View.GONE);
        tabOverlayView.setVisibility(tabIndex == 2 ? View.VISIBLE : View.GONE);

        navTabFront.setTextColor(tabIndex == 0 ? 0xFF00F0FF : 0xFF8B949E);
        navTabSettings.setTextColor(tabIndex == 1 ? 0xFF00F0FF : 0xFF8B949E);
        navTabOverlay.setTextColor(tabIndex == 2 ? 0xFF00F0FF : 0xFF8B949E);
    }

    private void setupSettings() {
        apiKeyInput.setText(openRouterClient.getApiKey());

        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, MODELS);
        modelSpinner.setAdapter(adapter);

        String currentModel = openRouterClient.getModel();
        modelNameText.setText(currentModel.substring(currentModel.indexOf("/") + 1));
        for (int i = 0; i < MODELS.length; i++) {
            if (MODELS[i].equals(currentModel)) {
                modelSpinner.setSelection(i);
                break;
            }
        }

        modelSpinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                openRouterClient.setModel(MODELS[position]);
                modelNameText.setText(MODELS[position].substring(MODELS[position].indexOf("/") + 1));
            }
            @Override public void onNothingSelected(AdapterView<?> parent) {}
        });

        btnSaveApiKey.setOnClickListener(v -> {
            String key = apiKeyInput.getText().toString().trim();
            openRouterClient.setApiKey(key);
            Toast.makeText(this, "API Key Saved", Toast.LENGTH_SHORT).show();
            refreshCredits();
        });

        btnPermAccessibility.setOnClickListener(v -> {
            startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));
            Toast.makeText(this, "Turn ON 'MJ-X Assistant' under Installed Services", Toast.LENGTH_LONG).show();
        });

        btnPermOverlay.setOnClickListener(v -> {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:" + getPackageName())));
            }
        });

        btnPermNotifications.setOnClickListener(v -> {
            startActivity(new Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS));
            Toast.makeText(this, "Enable 'MJ-X Assistant' to read notifications", Toast.LENGTH_LONG).show();
        });
    }

    private void setupFrontHUD() {
        btnVoiceListen.setOnClickListener(v -> startVoiceInteraction());

        btnReadNotifications.setOnClickListener(v -> {
            List<String> notifs = NotificationService.getRecentNotifications();
            if (notifs.isEmpty()) {
                appendLog("🔔 No new notifications captured yet.");
                voiceEngine.speak("Abhi koi naya notification ya call nahi aaya hai.");
            } else {
                StringBuilder sb = new StringBuilder("Recent alerts:\n");
                for (int i = Math.max(0, notifs.size() - 5); i < notifs.size(); i++) {
                    sb.append(notifs.get(i)).append("\n");
                }
                appendLog(sb.toString());
                voiceEngine.speak("Aapke paas " + notifs.size() + " alerts hain: " + notifs.get(notifs.size() - 1));
            }
        });

        btnScanScreen.setOnClickListener(v -> {
            MJAccessibilityService service = MJAccessibilityService.getInstance();
            if (service != null) {
                String hierarchy = service.getScreenHierarchyJson();
                appendLog("👁️ Scanned screen elements (" + hierarchy.length() + " chars)");
                processCommand("Scan and tell me what is currently displayed on this screen:\n" + hierarchy);
            } else {
                Toast.makeText(this, "Enable Accessibility in Settings first", Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void setupOverlayControls() {
        btnToggleFloatingHUD.setOnClickListener(v -> {
            Intent serviceIntent = new Intent(this, MJFloatingService.class);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(serviceIntent);
            } else {
                startService(serviceIntent);
            }
            Toast.makeText(this, "Floating Overlay HUD Online!", Toast.LENGTH_SHORT).show();
        });
    }

    private void startVoiceInteraction() {
        waveformText.setText("|||||||||| LISTENING... ||||||||||");
        agentStatusText.setText("LISTENING TO VOICE...");
        voiceEngine.startListening(new VoiceEngine.VoiceCallback() {
            @Override
            public void onSpeechRecognized(String text) {
                waveformText.setText("|||||||||| PROCESSING... ||||||||||");
                agentStatusText.setText("THINKING WITH OPENROUTER...");
                appendLog("🗣️ You: " + text);
                processCommand(text);
            }

            @Override public void onListeningStarted() {}
            @Override
            public void onListeningStopped() {
                waveformText.setText("|||| |||||||||| |||||| ||||||||||");
                agentStatusText.setText("24/7 AUTONOMOUS PHONE AGENT ONLINE");
            }

            @Override
            public void onError(String error) {
                waveformText.setText("|||| |||||||||| |||||| ||||||||||");
                agentStatusText.setText("24/7 AUTONOMOUS PHONE AGENT ONLINE");
                Toast.makeText(MainActivity.this, "Speech: " + error, Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void processCommand(String command) {
        String screenCtx = "";
        MJAccessibilityService service = MJAccessibilityService.getInstance();
        if (service != null) {
            screenCtx = service.getScreenHierarchyJson();
        }

        openRouterClient.sendPrompt(command, screenCtx, new OpenRouterClient.AgentCallback() {
            @Override
            public void onResponse(String textResponse, JSONObject toolCall) {
                appendLog("⚡ MJ-X: " + textResponse);
                voiceEngine.speak(textResponse);

                if (toolCall != null) {
                    appendLog("⚙️ Executing: " + toolCall.toString());
                    if (service != null) {
                        String res = service.executeTool(toolCall);
                        appendLog("✅ Result: " + res);
                    }
                }
            }

            @Override
            public void onError(String error) {
                appendLog("❌ Error: " + error);
                Toast.makeText(MainActivity.this, error, Toast.LENGTH_LONG).show();
            }
        });
    }

    private void appendLog(String log) {
        String current = transcriptLogText.getText().toString();
        transcriptLogText.setText(log + "\n\n" + current);
    }

    private void refreshCredits() {
        openRouterClient.fetchLiveCredits(new OpenRouterClient.CreditCallback() {
            @Override
            public void onSuccess(String creditInfo) {
                creditText.setText(creditInfo);
            }

            @Override
            public void onError(String error) {
                creditText.setText(error);
            }
        });
    }

    private void requestRequiredPermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            String[] perms = {
                    Manifest.permission.RECORD_AUDIO,
                    Manifest.permission.CALL_PHONE,
                    Manifest.permission.READ_CONTACTS,
                    Manifest.permission.SEND_SMS,
                    Manifest.permission.READ_SMS,
                    Manifest.permission.POST_NOTIFICATIONS
            };
            requestPermissions(perms, PERMISSION_REQ_CODE);
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (voiceEngine != null) voiceEngine.destroy();
    }
}
