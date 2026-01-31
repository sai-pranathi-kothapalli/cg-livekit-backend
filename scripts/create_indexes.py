#!/usr/bin/env python3
"""
Create MongoDB indexes for performance optimization.
Run from backend directory: python3 scripts/create_indexes.py
"""
import sys
from pathlib import Path

# Ensure backend root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_config
from app.db.mongo import get_database


def create_indexes():
    """Create all necessary indexes for the application."""
    config = get_config()
    db = get_database(config)
    
    print(f"Creating indexes for database: {db.name}")
    print("-" * 50)
    
    # Interview Bookings
    print("\n📁 Collection: interview_bookings")
    db.interview_bookings.create_index("token", unique=True)
    print("  ✅ Created unique index on 'token'")
    db.interview_bookings.create_index("email")
    print("  ✅ Created index on 'email'")
    db.interview_bookings.create_index("scheduled_at")
    print("  ✅ Created index on 'scheduled_at'")
    db.interview_bookings.create_index("status")
    print("  ✅ Created index on 'status'")
    db.interview_bookings.create_index("user_id")
    print("  ✅ Created index on 'user_id'")
    db.interview_bookings.create_index("slot_id")
    print("  ✅ Created index on 'slot_id'")
    db.interview_bookings.create_index([("email", 1), ("scheduled_at", -1)])
    print("  ✅ Created compound index on 'email' + 'scheduled_at'")
    
    # Students
    print("\n📁 Collection: students")
    db.students.create_index("email", unique=True)
    print("  ✅ Created unique index on 'email'")
    db.students.create_index("created_at")
    print("  ✅ Created index on 'created_at'")
    
    # Admin Users
    print("\n📁 Collection: admin_users")
    db.admin_users.create_index("username", unique=True)
    print("  ✅ Created unique index on 'username'")
    
    # Enrolled Users
    print("\n📁 Collection: enrolled_users")
    try:
        # Drop existing non-unique email index if it exists
        try:
            db.enrolled_users.drop_index("email_1")
            print("  ⚠️  Dropped existing non-unique 'email' index")
        except:
            pass
        db.enrolled_users.create_index("email", unique=True)
        print("  ✅ Created unique index on 'email'")
    except Exception as e:
        print(f"  ⚠️  Email index: {str(e)}")
    db.enrolled_users.create_index("created_at")
    print("  ✅ Created index on 'created_at'")
    
    # Interview Slots
    print("\n📁 Collection: interview_slots")
    db.interview_slots.create_index("date")
    print("  ✅ Created index on 'date'")
    db.interview_slots.create_index("start_time")
    print("  ✅ Created index on 'start_time'")
    db.interview_slots.create_index([("date", 1), ("start_time", 1)])
    print("  ✅ Created compound index on 'date' + 'start_time'")
    
    # Transcripts
    print("\n📁 Collection: interview_transcripts")
    db.interview_transcripts.create_index("booking_token")
    print("  ✅ Created index on 'booking_token'")
    db.interview_transcripts.create_index("room_name")
    print("  ✅ Created index on 'room_name'")
    db.interview_transcripts.create_index("created_at")
    print("  ✅ Created index on 'created_at'")
    
    # Evaluations
    print("\n📁 Collection: interview_evaluations")
    db.interview_evaluations.create_index("booking_token", unique=True)
    print("  ✅ Created unique index on 'booking_token'")
    db.interview_evaluations.create_index("evaluated_at")
    print("  ✅ Created index on 'evaluated_at'")
    
    # Round Evaluations
    print("\n📁 Collection: interview_round_evaluations")
    db.interview_round_evaluations.create_index("evaluation_id")
    print("  ✅ Created index on 'evaluation_id'")
    
    # Job Descriptions
    print("\n📁 Collection: job_descriptions")
    db.job_descriptions.create_index("updated_at")
    print("  ✅ Created index on 'updated_at'")
    
    # Application Forms
    print("\n📁 Collection: application_forms")
    db.application_forms.create_index("user_id")
    print("  ✅ Created index on 'user_id'")
    db.application_forms.create_index("email")
    print("  ✅ Created index on 'email'")
    
    # Assignments
    print("\n📁 Collection: assignments")
    db.assignments.create_index("user_id")
    print("  ✅ Created index on 'user_id'")
    db.assignments.create_index("slot_id")
    print("  ✅ Created index on 'slot_id'")
    db.assignments.create_index([("user_id", 1), ("slot_id", 1)], unique=True)
    print("  ✅ Created unique compound index on 'user_id' + 'slot_id'")
    
    print("\n" + "=" * 50)
    print("✅ All indexes created successfully!")
    print("=" * 50)
    
    # List all indexes
    print("\n📊 Index Summary:")
    for collection_name in db.list_collection_names():
        indexes = list(db[collection_name].list_indexes())
        if len(indexes) > 1:  # More than just _id index
            print(f"\n  {collection_name}:")
            for idx in indexes:
                if idx['name'] != '_id_':
                    print(f"    - {idx['name']}: {idx['key']}")


if __name__ == "__main__":
    create_indexes()
