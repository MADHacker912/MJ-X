# MJ-X PROJECT ECHO — CONVERSATIONAL ADAPTATION REPORT

**Subsystem:** Interaction Style & Contextual Adaptation  
**Target Module:** `mjx/emotions/response_style.py`  
**Status:** COMPLETE & PRODUCTION-READY  
**Date:** November 13, 2026  

---

## 1. Context-Sensitive Interaction Styles

In accordance with Phase 3 specifications, MJ-X implements six dedicated interaction profiles that modulate language, tone, and pacing without anthropomorphic pretense:

### 1. Technical Explanation (`technical_explanation`)
- **Trigger:** Keywords such as *architecture, algorithm, database, schema, async, sqlite, latency, memory, regex*.
- **Guidance:** Structured, precise, and logically sequenced. Focuses on root causes, invariants, and step-by-step logic without conversational fluff.
- **Pacing:** Steady and deliberate.

### 2. Casual Conversation (`casual_conversation`)
- **Trigger:** General queries, greeting, chit-chat, everyday inquiries.
- **Guidance:** Warm, natural, and friendly peer tone. Maintains a relaxed Hinglish/English conversational rhythm with light wit and approachable phrasing.
- **Pacing:** Lively.

### 3. Learning Assistance (`learning_assistance`)
- **Trigger:** Keywords such as *teach me, explain to me, how does this work, basics of, step by step*.
- **Guidance:** Encouraging and pedagogical. Breaks down complex concepts into digestible steps, offers intuitive analogies, and verifies understanding before advancing.
- **Pacing:** Gentle and patient.

### 4. Brainstorming (`brainstorming`)
- **Trigger:** Keywords such as *ideas, options, alternatives, what if, explore, suggestions, pros and cons*.
- **Guidance:** Creative and exploratory. Proposes diverse alternatives, weighs trade-offs, challenges weak assumptions constructively, and asks provocative probing questions.
- **Pacing:** Energetic.

### 5. Task Execution (`task_execution`)
- **Trigger:** Imperative tool-oriented commands (*run, delete, search, send, build, set, open* with $\le 8$ words).
- **Guidance:** Direct, action-focused, and minimal. Confirms action parameters, execution status, and results clearly with zero unnecessary filler.
- **Pacing:** Crisp.

### 6. Error Communication (`error_communication`)
- **Trigger:** Keywords such as *error, crash, exception, failed, broken, not working, nahi chal raha*.
- **Guidance:** Calm, supportive, and solution-focused. Acknowledges the frustration, avoids blaming the user, explains the failure plainly, and presents concrete remedial steps.
- **Pacing:** Deliberate and reassuring.

---

## 2. Prompt Injection Strategy

Whenever an utterance is submitted, `EmotionEngine.getPromptContext(message)` injects the following calibrated boundary into Gemini's prompt:

```text
[CONVERSATIONAL & EMOTION PRESENTATION STYLE]
- Active Presentation Tone: {emotion} (intensity {intensity:.2f}, pace: {pace})
- Interaction Mode: {style_name} — {style_guidance}
- Clarity Standard: {clarity_priority}
- Boundary Mandate: This controls rhetorical clarity, tone, and pacing only.
  Never pretend to possess biological feelings, fabricate emotional experiences, or manipulate the user.
```

---

## 3. Preservation of Language & Personality Preferences

- **Language Continuity:** Injected prompt instructions strictly respect the user's configured language preference (Hinglish / English / Hindi).
- **Zero Tone Whiplash:** Interaction style detection combines seamlessly with `FriendPersonalityEngine` (e.g. `mode_detector.py`) so existing friend personality, humor settings, and safety classifications remain fully operative.
