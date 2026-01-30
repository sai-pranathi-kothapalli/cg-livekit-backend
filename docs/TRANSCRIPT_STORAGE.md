# Transcript storage in MongoDB

## Where transcripts are stored

- **Database:** Same as the rest of the backend (e.g. `livekit_interview` if `MONGODB_DB_NAME=livekit_interview` in `.env`).
- **Collection:** `interview_transcripts` — **one document per interview** (per `booking_token`). Each document has a `messages` array; new messages are appended with `$push`.
- **Key field:** `booking_token` uniquely identifies the interview document.

**Why you don’t see `interview_transcripts` in Compass:** MongoDB creates a collection only when the first document is inserted. If no transcript has been saved yet (no interview finished with the worker writing to this DB), the collection doesn’t exist and won’t appear. To make it visible before any data, run:

```bash
cd Livekit-Backend-agent-backend
python3 scripts/create_transcript_collection.py
```

Then refresh Compass; `interview_transcripts` will show under the same database (e.g. `livekit_interview`).

## Who writes transcripts

| Source | When | Role | Code path |
|--------|------|------|-----------|
| **Agent (AI)** | When the agent finishes speaking a reply | `assistant` | Worker: `TranscriptStorageWrapper.send_transcript()` is called from the LLM/transcript pipeline (HistoryManagedLLMWrapper → transcript_service). Each agent utterance is forwarded to the frontend and saved to MongoDB. |
| **User (candidate)** | When STT finalizes the user’s speech | `user` | Worker: `entrypoint.py` → `on_user_input_transcribed` → `transcript_storage.save_transcript_message(..., role="user", ...)`. Only **final** transcripts are saved (not interim). |

Both paths use the **backend’s** `TranscriptStorageService` (same `interview_transcripts` collection). The worker loads the backend on `sys.path` and uses the same MongoDB config (env / `.env`) so it can write directly to that collection.

## Requirements for storage to work

1. **Worker** must have:
   - Backend on Python path (entrypoint and `transcript_storage_wrapper` add `Livekit-Backend-agent-backend`).
   - Same MongoDB env vars as the backend (e.g. `MONGODB_URI`, `MONGODB_DB_NAME`).

2. **Booking token** must be set:
   - For agent: set when creating the plugin (e.g. `plugin_service` passes `booking_token` into `TranscriptStorageWrapper`).
   - For user: passed into `_setup_session_event_handlers(..., booking_token, ...)` and used in `on_user_input_transcribed`.

If `booking_token` or the transcript service is missing, messages are not saved (code checks `if transcript_storage and booking_token` / `if self._storage_service and self._booking_token`).

## How to verify

1. **After an interview** — use the booking token from the interview URL or evaluation redirect:
   ```bash
   cd Livekit-Backend-agent-backend
   python scripts/verify_transcripts.py <booking_token>
   ```
   You should see both `assistant` and `user` messages in order.

2. **Recent activity** (no token):
   ```bash
   python scripts/verify_transcripts.py
   ```
   This lists recent documents in `interview_transcripts` grouped by `booking_token`.

3. **API** — the evaluation endpoint already loads the transcript by token:
   - `GET /api/evaluation/{token}` (or your evaluation route) uses `transcript_storage_service.get_transcript(token)` and returns it in the response. If the evaluation page shows the full conversation, transcripts are in MongoDB.

## Document shape (MongoDB) — one document per interview

```text
booking_token : str
room_name     : str
messages      : [
  { role, content, message_index, timestamp }, ...
]
created_at    : str (ISO)
updated_at    : str (ISO)
```

- **One document per interview:** All messages for an interview are stored in a single document. `save_transcript_message` uses `update_one` with `$push` to append to `messages`. Legacy documents (one doc per message) are still supported by `get_transcript`.
