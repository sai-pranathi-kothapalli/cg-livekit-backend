# API Documentation: STT, TTS, and LLM

This document describes the **Speech-to-Text (STT)**, **Text-to-Speech (TTS)**, and **LLM** APIs used by the LiveKit interview agent. The worker calls these services; configuration is via backend `.env`.

---

## Overview

| Service | Primary (self-hosted / Skillifire) | Fallback (cloud) |
|---------|-------------------------------------|-------------------|
| **STT** | `STT_BASE_URL` + `/stt/v1`          | Deepgram, ElevenLabs |
| **TTS** | `TTS_BASE_URL` + `/tts/v1`          | ElevenLabs |
| **LLM** | **With orchestrator:** `ORCHESTRATOR_BASE_URL` + `/chat/turn`<br>**Without orchestrator (direct):** `OPENAI_BASE_URL` + `/llm/v1` (OpenAI-compatible) | Grok (xAI), Gemini |

- **Orchestrator on** (`ORCHESTRATOR_LLM_ENABLED=true`): LLM is the orchestrator only; direct LLM and cloud fallbacks are not used for the agent.
- **Orchestrator off** (`ORCHESTRATOR_LLM_ENABLED=false`): LLM is **direct** self-hosted (`OPENAI_BASE_URL`/`llm/v1`), with optional fallback chain Gemini → Grok.

---

## Configuration (Environment Variables)

### Self-hosted / Skillifire (Primary)

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | API key for self-hosted STT/TTS/LLM | `litellm-master-key-change-in-production` |
| `OPENAI_BASE_URL` | Base URL for OpenAI-compatible LLM (backend use) | `https://ai.skillifire.com/api` |
| `STT_BASE_URL` | Base URL for STT service | `https://ai.skillifire.com/api` |
| `TTS_BASE_URL` | Base URL for TTS service | `https://ai.skillifire.com/api` |
| `OPENAI_STT_MODEL` | STT model name | `small.en` |
| `OPENAI_TTS_MODEL` | TTS model name | `kokoro` |
| `OPENAI_TTS_VOICE` | TTS voice ID | `af_bella` |
| `OPENAI_LLM_MODEL` | LLM model (when orchestrator disabled) | `qwen2-5-7b-instruct` |
| `SELF_HOSTED_STT_ENABLED` | Use self-hosted STT | `true` / `false` |
| `SELF_HOSTED_TTS_ENABLED` | Use self-hosted TTS | `true` / `false` |
| `SELF_HOSTED_LLM_ENABLED` | Use self-hosted LLM (only when orchestrator off) | `true` / `false` |

### Orchestrator (Primary LLM when enabled)

| Variable | Description | Example |
|----------|-------------|---------|
| `ORCHESTRATOR_BASE_URL` | Orchestrator API base URL | `https://ai.skillifire.com/api/orchestrator` |
| `ORCHESTRATOR_LLM_ENABLED` | Use orchestrator as sole LLM | `true` / `false` |

### Cloud fallbacks

| Variable | Description |
|----------|-------------|
| `DEEPGRAM_STT_ENABLED`, `DEEPGRAM_API_KEY` | Deepgram STT fallback |
| `ELEVENLABS_STT_ENABLED`, `ELEVENLABS_STT_API_KEY` | ElevenLabs STT fallback |
| `ELEVENLABS_TTS_ENABLED`, `ELEVENLABS_TTS_API_KEY`, `ELEVENLABS_TTS_VOICE_ID` | ElevenLabs TTS fallback |
| `GROK_LLM_ENABLED`, `XAI_API_KEY`, `GROK_MODEL` | xAI Grok LLM fallback |
| `GEMINI_LLM_ENABLED`, `GEMINI_API_KEY`, `GEMINI_MODEL` | Google Gemini LLM fallback |

---

## 1. LLM API (Orchestrator)

Used when `ORCHESTRATOR_LLM_ENABLED=true`. The worker sends each user turn to the orchestrator and receives the assistant reply.

**Base URL:** `ORCHESTRATOR_BASE_URL` (e.g. `https://ai.skillifire.com/api/orchestrator`)

### Endpoint

```
POST {ORCHESTRATOR_BASE_URL}/chat/turn
Content-Type: application/json
```

### Request body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | Yes | Room name or booking token; same ID = same conversation |
| `speaker` | string | Yes | Always `"user"` for user turn |
| `text` | string | Yes | User message text |
| `system_prompt` | string | No | System/instruction prompt for the model |
| `action_type` | string | No | `"interview"` (default): 6k context, 30 msgs, skip handling |
| `candidate_name` | string | No | Candidate name for context |
| `candidate_role` | string | No | Candidate role for context |

**Example**

```json
{
  "session_id": "booking_abc123",
  "speaker": "user",
  "text": "Tell me about your experience with banking.",
  "system_prompt": "You are an interview agent...",
  "action_type": "interview",
  "candidate_name": "Jane Doe",
  "candidate_role": "PO candidate"
}
```

### Response

| Field | Type | Description |
|-------|------|-------------|
| `response` | string | Assistant reply text |

**Example**

```json
{
  "response": "I have five years of experience in retail banking..."
}
```

### Errors

- **4xx/5xx:** `response.raise_for_status()` in worker; error text in response body.
- **Timeout:** 60 seconds (worker `httpx` client).

---

## 2. LLM API (Direct / Self-hosted, without orchestrator)

Used when `ORCHESTRATOR_LLM_ENABLED=false` and `SELF_HOSTED_LLM_ENABLED=true`. The worker calls the self-hosted LLM via the LiveKit OpenAI plugin, which uses an **OpenAI-compatible chat completions** API.

**Base URL:** `{OPENAI_BASE_URL}/llm/v1`  
**Example:** `https://ai.skillifire.com/api/llm/v1`

### Endpoint

```
POST {OPENAI_BASE_URL}/llm/v1/v1/chat/completions
Content-Type: application/json
Authorization: Bearer {OPENAI_API_KEY}
```

*(Exact path may be `/v1/chat/completions` or `/chat/completions` depending on the provider; the plugin uses the base URL above.)*

### Request body (OpenAI-compatible)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model` | string | Yes | `OPENAI_LLM_MODEL` (e.g. `qwen2-5-7b-instruct`) |
| `messages` | array | Yes | List of `{ "role": "system"|"user"|"assistant", "content": "..." }` |
| `stream` | boolean | No | `true` for streaming; worker typically uses streaming |
| `temperature` | number | No | Sampling temperature (e.g. 0.7) |

**Example**

```json
{
  "model": "qwen2-5-7b-instruct",
  "messages": [
    { "role": "system", "content": "You are an interview agent..." },
    { "role": "user", "content": "Tell me about your experience with banking." }
  ],
  "stream": true
}
```

### Response (OpenAI-compatible)

- **Streaming:** Server-Sent Events (SSE) with chunks; each chunk has `choices[0].delta.content` (or equivalent).
- **Non-streaming:** JSON with `choices[0].message.content` containing the full reply.

**Example (non-streaming)**

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "choices": [
    {
      "index": 0,
      "message": { "role": "assistant", "content": "I have five years of experience..." },
      "finish_reason": "stop"
    }
  ],
  "usage": { "prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80 }
}
```

### Fallback chain (when orchestrator is off)

1. **Primary:** Direct LLM at `OPENAI_BASE_URL/llm/v1` (above).
2. **First fallback:** Gemini (if `GEMINI_LLM_ENABLED=true`).
3. **Second fallback:** Grok (if `GROK_LLM_ENABLED=true`).

After 3 consecutive failures on primary, the worker switches to the next in the chain.

---

## 3. STT API (Speech-to-Text)

Self-hosted STT is called at **`{STT_BASE_URL}/stt/v1`**. The worker uses the LiveKit OpenAI plugin, which expects an **OpenAI Whisper–compatible** API.

### Base URL and path

```
Base URL: {STT_BASE_URL}/stt/v1
Example:  https://ai.skillifire.com/api/stt/v1
```

### Typical usage (worker)

- **Model:** `OPENAI_STT_MODEL` (e.g. `small.en`)
- **Input:** Audio stream (e.g. PCM) via the plugin’s `recognize()`; the plugin sends HTTP request(s) to the STT service.
- **No API key** in worker for STT (plugin uses `base_url` + `model` only in current setup).

### Expected API shape (Whisper-compatible)

If you implement or integrate a custom STT service, it should accept:

- **Method:** `POST`
- **Body:** `multipart/form-data` with an audio file (e.g. `file`) and optional `model`.
- **Response:** JSON with a `text` (or equivalent) field for the transcript.

Example response shape:

```json
{
  "text": "Transcribed speech here..."
}
```

Exact path (e.g. `/transcriptions` or `/v1/audio/transcriptions`) depends on the provider; the LiveKit OpenAI plugin uses the base URL and model you configure.

---

## 4. TTS API (Text-to-Speech)

Self-hosted TTS is called at **`{TTS_BASE_URL}/tts/v1`**. The worker uses the LiveKit OpenAI plugin with **API key**, **model**, and **voice**.

### Base URL and path

```
Base URL: {TTS_BASE_URL}/tts/v1
Example:  https://ai.skillifire.com/api/tts/v1
```

### Configuration (worker)

| Config | Env / value | Description |
|--------|-------------|-------------|
| Base URL | `TTS_BASE_URL` + `/tts/v1` | TTS API base |
| Model | `OPENAI_TTS_MODEL` | e.g. `kokoro` |
| Voice | `OPENAI_TTS_VOICE` | e.g. `af_bella` |
| API key | `OPENAI_API_KEY` | Sent in request (e.g. `Authorization: Bearer ...` or provider-specific header) |

### Expected API shape (OpenAI TTS–compatible)

- **Method:** `POST`
- **Headers:** `Authorization: Bearer {OPENAI_API_KEY}`, `Content-Type: application/json`
- **Body:** JSON with `model`, `input` (text), `voice` (optional)
- **Response:** Audio stream (e.g. `audio/mpeg` or `audio/pcm`) or JSON with audio URL/base64 depending on provider.

Example request:

```json
{
  "model": "kokoro",
  "input": "Hello, welcome to the interview.",
  "voice": "af_bella"
}
```

Exact path and field names depend on the provider (e.g. OpenAI TTS vs custom); the plugin uses the base URL, model, and voice you set in config.

---

## 5. Grok LLM (xAI) – Fallback

When orchestrator is disabled and Grok is enabled, the worker can use xAI’s API.

**Base URL:** `https://api.x.ai`  
**Endpoint:** `POST /v1/chat/completions`  
**Headers:** `Authorization: Bearer {XAI_API_KEY}`, `Content-Type: application/json`  
**Body:** OpenAI-compatible chat completions format (e.g. `model`, `messages`, `stream`).

---

## 6. Flow summary

1. **STT:** Worker receives audio → sends to `{STT_BASE_URL}/stt/v1` (Whisper-compatible) → gets transcript.
2. **LLM:**
   - **With orchestrator:** Worker sends user text to `{ORCHESTRATOR_BASE_URL}/chat/turn` → gets `response` → uses as assistant reply.
   - **Without orchestrator (direct):** Worker sends messages to `{OPENAI_BASE_URL}/llm/v1` (OpenAI-compatible chat completions) → gets streamed or full reply → uses as assistant reply; fallback chain Gemini → Grok on failure.
3. **TTS:** Worker sends assistant text to `{TTS_BASE_URL}/tts/v1` with model/voice and API key → gets audio → plays in room.

Fallbacks (Deepgram, ElevenLabs, Grok, Gemini) are used when primary STT/TTS/LLM fail or are disabled; see `.env` toggles and `worker/services/plugin_service.py`.

---

## References

- Worker STT/TTS/LLM setup: `worker/services/plugin_service.py`
- Orchestrator LLM client: `worker/services/orchestrator_llm.py`
- Backend config: `app/config.py`
- Env example: `Livekit-Backend-agent-backend/.env`
