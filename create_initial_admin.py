import sys
import os
import asyncio
from pathlib import Path

# Add backend directory to path so we can import app modules
backend_dir = Path(__file__).resolve().parent
sys.path.append(str(backend_dir))

from dotenv import load_dotenv
load_dotenv()

import bcrypt
# Mock the config/supabase import if needed, but we try to use app code
try:
    from app.db.supabase import get_supabase
    from app.utils.datetime_utils import get_now_ist
except ImportError:
    # Fallback if run from wrong directory, though sys.path should fix it
    print("Error imports. Make sure dependencies are installed.")
    sys.exit(1)

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

def create_initial_admin():
    print("--- Create Initial Admin User ---")
    
    # Try to load from environment variables first
    env_email = os.getenv("INITIAL_ADMIN_EMAIL")
    env_password = os.getenv("INITIAL_ADMIN_PASSWORD")
    env_username = os.getenv("INITIAL_ADMIN_USERNAME")
    
    # Allow command line args, then environment variables, then error
    if len(sys.argv) > 1:
        email = sys.argv[1]
        password = sys.argv[2] if len(sys.argv) > 2 else env_password
        username = sys.argv[3] if len(sys.argv) > 3 else env_username
    else:
        email = env_email
        password = env_password
        username = env_username

    if not email or not password or not username:
        print("❌ Error: Missing credentials.")
        print("Please provide them via command line arguments or environment variables:")
        print("  Usage: python create_initial_admin.py <email> <password> <username>")
        print("  Env: INITIAL_ADMIN_EMAIL, INITIAL_ADMIN_PASSWORD, INITIAL_ADMIN_USERNAME")
        sys.exit(1)
    
    print(f"Creating Admin -> Email: {email}, Username: {username}")
    
    try:
        supabase = get_supabase()
        
        # 1. Check if email or username exists
        print("Checking for existing user...")
        try:
            res_email = supabase.table("users").select("id").eq("email", email).execute()
            if res_email.data:
                print(f"⚠️  User with email {email} already exists.")
                return

            res_user = supabase.table("users").select("id").eq("username", username).execute()
            if res_user.data:
                print(f"⚠️  User with username {username} already exists.")
                return
        except Exception as e:
            print(f"Error checking users: {e}")
            return

        # 2. Hash password
        print("Hashing password...")
        hashed = hash_password(password)
        
        # 3. Insert
        print("Inserting into database...")
        
        data = {
            "email": email,
            "username": username,
            "password_hash": hashed,
            "role": "admin",
            "name": "System Admin",
            "created_at": get_now_ist().isoformat(),
            "updated_at": get_now_ist().isoformat()
        }
        
        res = supabase.table("users").insert(data).execute()
        
        if res.data:
            print(f"✅ Success! Admin user created.")
            print(f"Email: {email}")
            print(f"Password: {password}")
            print(f"Login at the Admin Portal.")
        else:
            print("❌ Failed to create user (no data returned).")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    create_initial_admin()
