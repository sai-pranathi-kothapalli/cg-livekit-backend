#!/usr/bin/env python3
"""
Test that the backend can write a transcript to MongoDB (same path the worker uses).

Run from backend root:
  python3 scripts/test_transcript_save.py

If this works but interviews still don't store transcripts, the issue is in the worker
(booking_token, transcript_storage init, or room name).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_config
from app.services.transcript_storage_service import TranscriptStorageService


def main():
    config = get_config()
    db_name = getattr(config.mongo, "db_name", None) or "interview"
    print(f"Using MongoDB database: {db_name}")
    service = TranscriptStorageService(config)
    test_token = "test_write_verify"
    ok = service.save_transcript_message(
        booking_token=test_token,
        room_name="test_room",
        role="user",
        content="Test message to verify transcript storage.",
        message_index=0,
        timestamp=None,
    )
    if not ok:
        print("❌ save_transcript_message returned False")
        return
    print("✅ Wrote one test document to interview_transcripts")
    # Fetch it back
    transcript = service.get_transcript(test_token)
    print(f"✅ Read back {len(transcript)} message(s)")
    if transcript:
        print(f"   Content: {transcript[0].get('content', '')[:60]}...")
    print("\nIf interviews still don't store transcripts, check worker logs for:")
    print("  - 'TranscriptStorageService initialized' (good)")
    print("  - 'Failed to initialize TranscriptStorageService' (bad)")
    print("  - 'Saved transcript' / 'Failed to save transcript'")
    print("  - Room name should be like 'interview_<token>' so booking_token is set.")


if __name__ == "__main__":
    main()
