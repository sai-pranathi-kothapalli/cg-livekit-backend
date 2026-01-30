#!/usr/bin/env python3
"""
Verify that interview transcripts are stored in MongoDB.

Usage:
  # List recent transcripts (last 20 docs, grouped by booking_token)
  python scripts/verify_transcripts.py

  # Show full transcript for a specific booking token
  python scripts/verify_transcripts.py <booking_token>

Requires: Same .env / MongoDB config as the backend (run from backend root).
"""

import sys
import os

# Run from backend root so app is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_config
from app.db.mongo import get_database
from app.services.transcript_storage_service import TranscriptStorageService


def main():
    config = get_config()
    service = TranscriptStorageService(config)
    col = service.col

    if len(sys.argv) >= 2:
        booking_token = sys.argv[1].strip()
        print(f"\n=== Transcript for booking_token: {booking_token} ===\n")
        transcript = service.get_transcript(booking_token)
        if not transcript:
            print("No transcript messages found for this token.")
            print("Check that the worker is using the same MongoDB and that booking_token is passed correctly.")
            return
        print(f"Found {len(transcript)} message(s):\n")
        for i, msg in enumerate(transcript):
            role = msg.get("role", "?")
            content = (msg.get("content") or "")[:200]
            if len((msg.get("content") or "")) > 200:
                content += "..."
            idx = msg.get("index", i)
            ts = msg.get("timestamp", "")
            print(f"  [{idx}] {role}: {content}")
            print(f"       timestamp: {ts}")
        print("\n✅ Transcript is stored in MongoDB (collection: interview_transcripts).")
        return

    # No token: show recent activity (one doc per interview; sort by updated_at or created_at)
    print("\n=== Recent transcript activity (MongoDB: interview_transcripts) ===\n")
    cursor = col.find({}).sort("updated_at", -1).limit(50)
    docs = list(cursor)
    if not docs:
        # Fallback: legacy sort by timestamp
        cursor = col.find({}).sort("timestamp", -1).limit(50)
        docs = list(cursor)
    if not docs:
        print("No transcript documents found in interview_transcripts.")
        print("Run an interview and ensure the worker has MongoDB config (same as backend).")
        return

    print(f"Sample of recent docs (one document per interview; total: {len(docs)}):\n")
    for d in docs[:15]:
        tok = d.get("booking_token", "?")
        if "messages" in d and isinstance(d["messages"], list):
            msg_count = len(d["messages"])
            roles = [m.get("role") or m.get("message_role") for m in d["messages"][:3]]
        else:
            msg_count = 1
            roles = [d.get("message_role", "?")]
        print(f"  booking_token: {tok}")
        print(f"    message_count: {msg_count}, roles sample: {roles}")
        print()
    print("To see full transcript for a token: python scripts/verify_transcripts.py <booking_token>")
    print("✅ Transcripts are being stored in MongoDB (one document per interview).")


if __name__ == "__main__":
    main()
