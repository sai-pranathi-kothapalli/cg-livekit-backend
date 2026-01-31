#!/usr/bin/env python3
"""
Seed admin user in MongoDB.
Run from backend directory: python3 seed_admin.py

Set ADMIN_INITIAL_PASSWORD in environment before running.
Example: ADMIN_INITIAL_PASSWORD="YourSecurePassword123!" python3 seed_admin.py
"""
import os
import sys
from pathlib import Path

# Ensure backend root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bcrypt
from app.config import get_config
from app.db.mongo import get_database
from app.utils.datetime_utils import get_now_ist


def main():
    config = get_config()
    db = get_database(config)
    db_name = db.name
    col = db["admin_users"]

    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_INITIAL_PASSWORD")
    
    if not password:
        print("ERROR: ADMIN_INITIAL_PASSWORD environment variable is required.")
        print("Usage: ADMIN_INITIAL_PASSWORD='YourSecurePassword123!' python3 seed_admin.py")
        sys.exit(1)
    
    if len(password) < 12:
        print("ERROR: ADMIN_INITIAL_PASSWORD must be at least 12 characters long.")
        sys.exit(1)
    
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    now = get_now_ist().isoformat()

    doc = {
        "username": username,
        "password_hash": password_hash,
        "created_at": now,
        "updated_at": now,
    }

    result = col.update_one(
        {"username": username},
        {"$set": {**doc}},
        upsert=True,
    )
    print(f"Database: {db_name}")
    if result.upserted_id:
        print(f"Created admin user: username={username}")
    else:
        print(f"Updated admin user: username={username}")
    print("Password has been set from ADMIN_INITIAL_PASSWORD environment variable.")
    print("Next: Start the backend and add users via the admin UI or API.")
    print("Done.")


if __name__ == "__main__":
    main()
