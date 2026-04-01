# API Documentation: STT, TTS, and LLM

This document describes the **Speech-to-Text (STT)**, **Text-to-Speech (TTS)**, and **LLM** APIs used by the LiveKit interview agent. The worker calls these services; configuration is via backend `.env`.

---

## Overview

| Service | Configuration |
|---------|----------------|
| **LLM** | **Primary:** Google Gemini (`GEMINI_API_KEY`, `GEMINI_MODEL`). **Fallback:** self-hosted Qwen at `OPENAI_BASE_URL`/`llm/v1` (after 3 Gemini failures). |
| **STT** | **Option 1 (Self-hosted):** `STT_BASE_URL` + `/stt/v1` (Whisper-compatible). **Option 2 (Cloud):** ElevenLabs (`ELEVENLABS_STT_ENABLED=true`). |
| **TTS** | **Option 1 (Self-hosted):** `TTS_BASE_URL` + `/tts/v1` (OpenAI-compatible). **Option 2 (Cloud):** ElevenLabs (`ELEVENLABS_TTS_ENABLED=true`). |

- **LLM:** Gemini is the primary LLM; self-hosted Qwen is the only fallback (no Grok, no other cloud LLMs).
- **STT:** Can be self-hosted or ElevenLabs.
- **TTS:** Can be self-hosted or ElevenLabs.

---

## Configuration (Environment Variables)

### Required

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini API key (primary LLM). **Required.** |
| `GEMINI_MODEL` | Gemini model name (e.g. `gemini-1.5-flash`, `gemini-2.5-flash`). |
| `OPENAI_API_KEY` | API key for self-hosted STT/TTS and Qwen LLM fallback. |
| `OPENAI_BASE_URL` | Base URL for self-hosted APIs. |
| `STT_BASE_URL` | Base URL for STT service. |
| `TTS_BASE_URL` | Base URL for TTS service. |

### Self-hosted (STT, TTS, and LLM fallback)

| Variable | Description |
|----------|-------------|
| `OPENAI_STT_MODEL` | STT model name (e.g. `small.en`). |
| `OPENAI_TTS_MODEL` | TTS model name (e.g. `kokoro`). |
| `OPENAI_TTS_VOICE` | TTS voice ID (e.g. `af_bella`). |
| `OPENAI_LLM_MODEL` | Qwen model for LLM fallback (e.g. `qwen2-5-7b-instruct`). |
| `SELF_HOSTED_STT_ENABLED` | Use self-hosted STT (mutual exclusion with `ELEVENLABS_STT_ENABLED`). |
| `SELF_HOSTED_TTS_ENABLED` | Use self-hosted TTS (mutual exclusion with `ELEVENLABS_TTS_ENABLED`). |
| `SELF_HOSTED_LLM_ENABLED` | Enable Qwen as LLM fallback (`true` recommended). |

### ElevenLabs (STT and TTS)
| Variable | Description |
|----------|-------------|
| `ELEVENLABS_TTS_API_KEY` | API key for ElevenLabs. |
| `ELEVENLABS_STT_ENABLED` | Use ElevenLabs STT (mutual exclusion with `SELF_HOSTED_STT_ENABLED`). |
| `ELEVENLABS_STT_MODEL` | ElevenLabs STT model name (e.g. `eleven_multilingual_v2`). |
| `ELEVENLABS_TTS_ENABLED` | Use ElevenLabs TTS (mutual exclusion with `SELF_HOSTED_TTS_ENABLED`). |
| `ELEVENLABS_VOICE_ID` | Voice ID for ElevenLabs TTS. |
| `ELEVENLABS_MODEL` | Model for ElevenLabs TTS. |

---

## 1. LLM: Google Gemini (Primary)

The worker uses **Google Gemini** as the primary LLM. The LiveKit Google plugin calls the Gemini API.

- **Primary:** Gemini (required).
- **Fallback:** Self-hosted Qwen at `{OPENAI_BASE_URL}/llm/v1` (used after 3 consecutive Gemini failures if `SELF_HOSTED_LLM_ENABLED=true`).

Configuration: `GEMINI_API_KEY`, `GEMINI_MODEL`. Fallback uses `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_LLM_MODEL`.

---

## 2. LLM Fallback: Self-hosted Qwen

When Gemini fails 3 times in a row, the worker switches to the self-hosted **Qwen** LLM (OpenAI-compatible).

**Base URL:** `{OPENAI_BASE_URL}/llm/v1`

- **Method:** POST (OpenAI-compatible chat completions).
- **Headers:** `Authorization: Bearer {OPENAI_API_KEY}`, `Content-Type: application/json`.
- **Body:** `model`, `messages`, optional `stream`, `temperature`.

---

## 3. STT (Speech-to-Text)

The worker supports either Self-hosted STT or ElevenLabs STT.

### Option 1: Self-hosted STT
Self-hosted STT at **`{STT_BASE_URL}/stt/v1`**. Worker uses the LiveKit OpenAI plugin with a Whisper-compatible API.

- **Model:** `OPENAI_STT_MODEL` (e.g. `small.en`).
- **Input:** Audio stream via plugin `recognize()`.
- Expected API: POST, `multipart/form-data` with audio file, response JSON with `text` (or equivalent).

### Option 2: ElevenLabs STT
The worker uses the LiveKit ElevenLabs plugin. Set `ELEVENLABS_STT_ENABLED=true` and provide `ELEVENLABS_TTS_API_KEY` and `ELEVENLABS_STT_MODEL`.

---

## 4. TTS (Text-to-Speech) – Self-hosted only

Self-hosted TTS at **`{TTS_BASE_URL}/tts/v1`**. Worker uses the LiveKit OpenAI plugin with API key, model, and voice.

- **Base URL:** `TTS_BASE_URL` + `/tts/v1`
- **Model:** `OPENAI_TTS_MODEL` (e.g. `kokoro`)
- **Voice:** `OPENAI_TTS_VOICE` (e.g. `af_bella`)
- **API key:** `OPENAI_API_KEY`

Expected: POST, JSON body with `model`, `input` (text), `voice`; response audio stream or URL/base64.

---

## 5. Flow summary

1. **STT:** Worker receives audio → sends to ElevenLabs or `{STT_BASE_URL}/stt/v1` → gets transcript.
2. **LLM:** Worker sends messages to **Gemini** (primary). On 3 consecutive failures, falls back to **Qwen** at `{OPENAI_BASE_URL}/llm/v1` if enabled.
3. **TTS:** Worker sends assistant text to ElevenLabs or `{TTS_BASE_URL}/tts/v1` → gets audio → plays in room.

No other cloud STT/TTS/LLM services are used.

---

## References

- Worker STT/TTS/LLM setup: `worker/services/plugin_service.py`
- Backend config: `app/config.py`
- Env example: `Livekit-Backend-agent-backend/.env`
