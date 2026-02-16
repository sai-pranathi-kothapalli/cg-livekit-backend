import sys
import os

# Add backend to path
sys.path.append(os.getcwd())

print("Verifying imports...")

try:
    print("Importing app.api.main...")
    from app.api import main
    print("✅ app.api.main imported")

    print("Importing app.api.auth...")
    from app.api import auth
    print("✅ app.api.auth imported")

    print("Importing app.api.admin...")
    from app.api import admin
    print("✅ app.api.admin imported")

    print("Importing app.api.bookings...")
    from app.api import bookings
    print("✅ app.api.bookings imported")
    
    print("Importing app.api.interviews...")
    from app.api import interviews
    print("✅ app.api.interviews imported")

    print("Importing app.api.slots...")
    from app.api import slots
    print("✅ app.api.slots imported")

    print("Importing app.api.users...")
    from app.api import users
    print("✅ app.api.users imported")

    print("Importing app.api.resume...")
    from app.api import resume
    print("✅ app.api.resume imported")
    
    print("Importing app.api.student...")
    from app.api import student
    print("✅ app.api.student imported")

    print("🚀 All imports successful!")

except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)
