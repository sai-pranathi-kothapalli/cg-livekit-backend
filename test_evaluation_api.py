#!/usr/bin/env python3
"""
Test script to verify evaluation API endpoint is working.

Usage:
    python test_evaluation_api.py [booking_token]
"""

import sys
import requests
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.config import get_config
from app.services.booking_service import BookingService
from app.services.transcript_storage_service import TranscriptStorageService
from app.services.evaluation_service import EvaluationService

def test_evaluation_system():
    """Test the evaluation system components."""
    print("=" * 60)
    print("Testing Evaluation System")
    print("=" * 60)
    
    config = get_config()
    
    # Test 1: Check services can be initialized
    print("\n[1] Testing service initialization...")
    try:
        booking_service = BookingService(config)
        transcript_service = TranscriptStorageService(config)
        evaluation_service = EvaluationService(config)
        print("✅ All services initialized successfully")
    except Exception as e:
        print(f"❌ Service initialization failed: {e}")
        return False
    
    # Test 2: Check database connection (try to query tables)
    print("\n[2] Testing database connection...")
    try:
        # Try to get a booking (this tests DB connection)
        bookings = booking_service.get_all_bookings()
        print(f"✅ Database connection successful (found {len(bookings)} bookings)")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
    
    # Test 3: Check if tables exist (by trying to query them)
    print("\n[3] Testing table access...")
    try:
        # Try to get transcript (should return empty list if table exists)
        test_token = "test_token_12345"
        transcript = transcript_service.get_transcript(test_token)
        print(f"✅ interview_transcripts table accessible (returned {len(transcript)} transcripts)")
        
        # Try to get evaluation (should return None if table exists)
        evaluation = evaluation_service.get_evaluation(test_token)
        print(f"✅ interview_evaluations table accessible (evaluation: {evaluation is None})")
    except Exception as e:
        print(f"❌ Table access failed: {e}")
        print(f"   Error details: {type(e).__name__}: {str(e)}")
        return False
    
    # Test 4: Test API endpoint (if server is running)
    print("\n[4] Testing API endpoint...")
    api_url = f"http://localhost:8000/api/evaluation/test_token"
    try:
        response = requests.get(api_url, timeout=5)
        if response.status_code == 404:
            print("✅ API endpoint is working (404 expected for non-existent token)")
        elif response.status_code == 200:
            print("✅ API endpoint is working (200 response)")
        else:
            print(f"⚠️  API returned status {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("⚠️  Backend server not running (start with: python backend_server.py)")
    except Exception as e:
        print(f"⚠️  API test error: {e}")
    
    # Test 5: Test with actual booking token if provided
    if len(sys.argv) > 1:
        booking_token = sys.argv[1]
        print(f"\n[5] Testing with booking token: {booking_token}")
        try:
            booking = booking_service.get_booking(booking_token)
            if booking:
                print(f"✅ Booking found: {booking.get('name', 'N/A')}")
                
                transcript = transcript_service.get_transcript(booking_token)
                print(f"   Transcript messages: {len(transcript)}")
                
                evaluation = evaluation_service.get_evaluation(booking_token)
                if evaluation:
                    print(f"✅ Evaluation found:")
                    print(f"   Overall score: {evaluation.get('overall_score')}")
                    print(f"   Rounds completed: {evaluation.get('rounds_completed')}")
                    print(f"   Duration: {evaluation.get('duration_minutes')} minutes")
                else:
                    print("   No evaluation found (this is normal for new interviews)")
            else:
                print(f"❌ Booking not found for token: {booking_token}")
        except Exception as e:
            print(f"❌ Error testing with booking token: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Evaluation system verification complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Run an interview to generate transcripts")
    print("2. Check evaluation page at: /evaluation/{token}")
    print("3. Verify data appears in Supabase tables")
    
    return True

if __name__ == "__main__":
    try:
        test_evaluation_system()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
