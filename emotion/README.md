# MJ Emotion Engine

The package models a temporary, simulated response style. It does not claim that
MJ has human feelings and it does not persist transient user moods.

## Modules

- `state.py`: validated state object and supported vocabulary
- `detection.py`: contextual local detection plus validated AI classifier input/output
- `transitions.py`: gradual transitions and time-based decay
- `avatar.py`: UI-neutral expression and animation mappings
- `voice.py`: voice, typing, and PCM playback settings
- `memory.py`: explicit, stable response-preference learning only
- `engine.py`: thread-safe orchestration and public developer API

## Settings

The following optional keys are read from `config/api_keys.json` at startup:

```json
{
  "emotion_engine_enabled": true,
  "avatar_emotions_enabled": true,
  "voice_emotions_enabled": true,
  "emotion_intensity": 0.8,
  "emoji_frequency": "low",
  "emotion_decay_time": 180,
  "allow_emotion_memory": true
}
```

Use `memory.config_manager.save_emotion_settings(...)` to validate and update
these values without replacing other application configuration.
