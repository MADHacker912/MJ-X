package com.mjx.assistant;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class OpenRouterClient {

    private static final String TAG = "OpenRouterClient";
    private static final String PREF_NAME = "mjx_prefs";
    private static final String KEY_API_KEY = "openrouter_api_key";
    private static final String KEY_MODEL = "openrouter_model";

    public static final String DEFAULT_MODEL = "google/gemini-2.0-flash-exp:free";

    private final Context context;
    private final SharedPreferences prefs;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    public interface CreditCallback {
        void onSuccess(String creditInfo);
        void onError(String error);
    }

    public interface AgentCallback {
        void onResponse(String textResponse, JSONObject toolCall);
        void onError(String error);
    }

    public OpenRouterClient(Context context) {
        this.context = context.getApplicationContext();
        this.prefs = this.context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE);
    }

    public void setApiKey(String apiKey) {
        prefs.edit().putString(KEY_API_KEY, apiKey.trim()).apply();
    }

    public String getApiKey() {
        return prefs.getString(KEY_API_KEY, "");
    }

    public void setModel(String model) {
        prefs.edit().putString(KEY_MODEL, model.trim()).apply();
    }

    public String getModel() {
        return prefs.getString(KEY_MODEL, DEFAULT_MODEL);
    }

    /**
     * Checks live OpenRouter API credits and usage
     */
    public void fetchLiveCredits(CreditCallback callback) {
        final String apiKey = getApiKey();
        if (apiKey.isEmpty()) {
            callback.onError("No API Key");
            return;
        }

        executor.execute(() -> {
            try {
                URL url = new URL("https://openrouter.ai/api/v1/auth/key");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("GET");
                conn.setRequestProperty("Authorization", "Bearer " + apiKey);
                conn.setConnectTimeout(5000);
                conn.setReadTimeout(5000);

                int code = conn.getResponseCode();
                if (code == 200) {
                    BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                    StringBuilder sb = new StringBuilder();
                    String line;
                    while ((line = reader.readLine()) != null) sb.append(line);
                    reader.close();

                    JSONObject json = new JSONObject(sb.toString()).getJSONObject("data");
                    double usage = json.optDouble("usage", 0.0);
                    double limit = json.optDouble("limit", 0.0);
                    boolean isFreeTier = json.optBoolean("is_free_tier", false);

                    String info;
                    if (isFreeTier) {
                        info = "Free Tier (Active)";
                    } else if (limit > 0) {
                        double remaining = Math.max(0.0, limit - usage);
                        info = String.format("$%.2f Left", remaining);
                    } else {
                        info = String.format("$%.2f Used", usage);
                    }

                    mainHandler.post(() -> callback.onSuccess(info));
                } else {
                    mainHandler.post(() -> callback.onError("HTTP " + code));
                }
                conn.disconnect();
            } catch (Exception e) {
                mainHandler.post(() -> callback.onError("Network error"));
            }
        });
    }

    /**
     * Sends prompt to OpenRouter and returns agent decision + optional autonomous tool call
     */
    public void sendPrompt(String userPrompt, String screenContext, AgentCallback callback) {
        final String apiKey = getApiKey();
        if (apiKey.isEmpty()) {
            callback.onError("Please set OpenRouter API key in Settings");
            return;
        }

        executor.execute(() -> {
            try {
                URL url = new URL("https://openrouter.ai/api/v1/chat/completions");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setRequestProperty("Authorization", "Bearer " + apiKey);
                conn.setRequestProperty("HTTP-Referer", "https://github.com/MADHacker912/MJ-X");
                conn.setRequestProperty("X-Title", "MJ-X Android Agent");
                conn.setDoOutput(true);
                conn.setConnectTimeout(15000);
                conn.setReadTimeout(30000);

                String systemPrompt = "You are MJ-X, an autonomous AI desktop and phone agent operating natively on an Android device. "
                        + "You speak Hinglish/English. You have autonomous device control tools. "
                        + "When the user asks you to do something (open app, call, whatsapp, tap, type, read notification), you must answer with a JSON tool action if an action is needed.\n"
                        + "Tool formats:\n"
                        + "1. {\"tool\": \"open_app\", \"app\": \"whatsapp|youtube|settings|dialer|camera|spotify|chrome|...\"}\n"
                        + "2. {\"tool\": \"make_call\", \"contact\": \"Name or phone number\"}\n"
                        + "3. {\"tool\": \"send_whatsapp\", \"contact\": \"Name\", \"message\": \"text\"}\n"
                        + "4. {\"tool\": \"click_text\", \"text\": \"Button or label text to tap\"}\n"
                        + "5. {\"tool\": \"type\", \"text\": \"text to enter\"}\n"
                        + "6. {\"tool\": \"navigate\", \"action\": \"home|back|notifications\"}\n"
                        + "Always keep spoken replies short, natural, and helpful. "
                        + "If you trigger a tool, provide your conversational reply first, followed by [ACTION: <json>].";

                JSONObject req = new JSONObject();
                req.put("model", getModel());

                JSONArray messages = new JSONArray();
                JSONObject sysMsg = new JSONObject();
                sysMsg.put("role", "system");
                sysMsg.put("content", systemPrompt);
                messages.put(sysMsg);

                if (screenContext != null && !screenContext.isEmpty()) {
                    JSONObject ctxMsg = new JSONObject();
                    ctxMsg.put("role", "system");
                    ctxMsg.put("content", "Current phone screen elements:\n" + screenContext);
                    messages.put(ctxMsg);
                }

                JSONObject usrMsg = new JSONObject();
                usrMsg.put("role", "user");
                usrMsg.put("content", userPrompt);
                messages.put(usrMsg);

                req.put("messages", messages);
                req.put("temperature", 0.7);

                OutputStream os = conn.getOutputStream();
                os.write(req.toString().getBytes("utf-8"));
                os.close();

                int code = conn.getResponseCode();
                if (code == 200) {
                    BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                    StringBuilder sb = new StringBuilder();
                    String line;
                    while ((line = reader.readLine()) != null) sb.append(line);
                    reader.close();

                    JSONObject respJson = new JSONObject(sb.toString());
                    String content = respJson.getJSONArray("choices")
                            .getJSONObject(0)
                            .getJSONObject("message")
                            .getString("content");

                    // Parse optional [ACTION: {...}]
                    JSONObject toolCall = null;
                    String textReply = content;
                    int actionIdx = content.indexOf("[ACTION:");
                    if (actionIdx != -1) {
                        textReply = content.substring(0, actionIdx).trim();
                        int endIdx = content.indexOf("]", actionIdx);
                        if (endIdx != -1) {
                            String jsonStr = content.substring(actionIdx + 8, endIdx).trim();
                            try {
                                toolCall = new JSONObject(jsonStr);
                            } catch (Exception ignored) {}
                        }
                    }

                    final String finalText = textReply;
                    final JSONObject finalTool = toolCall;
                    mainHandler.post(() -> callback.onResponse(finalText, finalTool));
                } else {
                    mainHandler.post(() -> callback.onError("OpenRouter Error: HTTP " + code));
                }
                conn.disconnect();
            } catch (Exception e) {
                Log.e(TAG, "OpenRouter call failed", e);
                mainHandler.post(() -> callback.onError("Failed: " + e.getMessage()));
            }
        });
    }
}
