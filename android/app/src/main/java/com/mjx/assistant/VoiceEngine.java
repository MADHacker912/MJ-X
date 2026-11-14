package com.mjx.assistant;

import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.util.Log;

import java.util.ArrayList;
import java.util.Locale;

public class VoiceEngine {

    private static final String TAG = "VoiceEngine";

    private final Context context;
    private TextToSpeech tts;
    private SpeechRecognizer recognizer;
    private boolean isTtsReady = false;

    public interface VoiceCallback {
        void onSpeechRecognized(String text);
        void onListeningStarted();
        void onListeningStopped();
        void onError(String error);
    }

    public VoiceEngine(Context context) {
        this.context = context.getApplicationContext();
        initTts();
    }

    private void initTts() {
        tts = new TextToSpeech(context, status -> {
            if (status == TextToSpeech.SUCCESS) {
                int res = tts.setLanguage(new Locale("hi", "IN"));
                if (res == TextToSpeech.LANG_MISSING_DATA || res == TextToSpeech.LANG_NOT_SUPPORTED) {
                    tts.setLanguage(Locale.US);
                }
                tts.setPitch(1.05f);
                tts.setSpeechRate(1.0f);
                isTtsReady = true;
                Log.i(TAG, "TTS Initialized successfully.");
            }
        });
    }

    public void speak(String text) {
        if (isTtsReady && tts != null && text != null && !text.isEmpty()) {
            tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "mjx_speech");
        }
    }

    public void stopSpeaking() {
        if (tts != null) {
            tts.stop();
        }
    }

    public void startListening(VoiceCallback callback) {
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            callback.onError("Speech recognition not available on device");
            return;
        }

        if (recognizer == null) {
            recognizer = SpeechRecognizer.createSpeechRecognizer(context);
        }

        recognizer.setRecognitionListener(new RecognitionListener() {
            @Override public void onReadyForSpeech(Bundle params) { callback.onListeningStarted(); }
            @Override public void onBeginningOfSpeech() {}
            @Override public void onRmsChanged(float rmsdB) {}
            @Override public void onBufferReceived(byte[] buffer) {}
            @Override public void onEndOfSpeech() { callback.onListeningStopped(); }
            @Override
            public void onError(int error) {
                callback.onListeningStopped();
                callback.onError("Speech error code: " + error);
            }

            @Override
            public void onResults(Bundle results) {
                callback.onListeningStopped();
                ArrayList<String> matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                if (matches != null && !matches.isEmpty()) {
                    callback.onSpeechRecognized(matches.get(0));
                }
            }

            @Override public void onPartialResults(Bundle partialResults) {}
            @Override public void onEvent(int eventType, Bundle params) {}
        });

        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-IN");
        intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
        recognizer.startListening(intent);
    }

    public void destroy() {
        if (tts != null) {
            tts.stop();
            tts.shutdown();
        }
        if (recognizer != null) {
            recognizer.destroy();
        }
    }
}
