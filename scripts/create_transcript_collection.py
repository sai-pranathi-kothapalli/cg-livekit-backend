#!/usr/bin/env python3
"""
Create the interview_transcripts collection in MongoDB so it appears in Compass.

MongoDB only creates a collection when the first document is inserted. If no
transcript has been saved yet, interview_transcripts won't show up. This script
creates the collection (empty) so you can see it in Compass under livekit_interview.

Run from backend root:
  python3 scripts/create_transcript_collection.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_config
from app.services.transcript_storage_service import TranscriptStorageService


def main():
    config = get_config()
    service = TranscriptStorageService(config)
    db = service.db
    name = "interview_transcripts"
    if name in db.list_collection_names():
        print(f"Collection '{name}' already exists in database '{db.name}'.")
        return
    db.create_collection(name)
    print(f"Created collection '{name}' in database '{db.name}'.")
    print("You should now see it in MongoDB Compass under the same database.")


if __name__ == "__main__":
    main()
