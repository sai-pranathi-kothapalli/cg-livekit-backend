# Setup Instructions

## Database Setup

### Step 1: Run SQL Migration in Supabase

1. Go to your Supabase Dashboard
2. Navigate to SQL Editor
3. Run the SQL from `migration_create_tables.sql`

This will create:
- `job_descriptions` table (for storing job descriptions)
- `admin_users` table (for storing admin credentials)

### Step 2: Create Default Admin User

The migration will create a default admin user:
- **Username:** `admin`
- **Password:** `Admin@123`

**⚠️ IMPORTANT:** Change this password immediately after first login in production!

Alternatively, you can run the seed script:
```bash
cd backend
python seed_admin.py
```

To create a new admin user with a custom password, run this in Python:

```python
from app.services.admin_service import AdminService
from app.config import get_config

config = get_config()
admin_service = AdminService(config)

# Create new admin
admin_service.create_admin_user("new_admin", "secure_password")
```

Or generate a bcrypt hash and insert directly:

```python
import bcrypt
hash = bcrypt.hashpw('your_password'.encode(), bcrypt.gensalt()).decode()
print(hash)
```

Then insert into Supabase:
```sql
INSERT INTO admin_users (username, password_hash)
VALUES ('new_admin', '<generated_hash>');
```

## Changes Made

### 1. Fixed Upload Application 422 Error
- Added better error handling in upload endpoint
- Added validation for empty files
- Improved error messages

### 2. Job Description Persistence
- Created `JobDescriptionService` to handle JD CRUD operations
- JD is now stored in Supabase `job_descriptions` table
- Updates persist to database

### 3. Admin Authentication
- Removed hardcoded credentials from code
- Created `AdminService` with bcrypt password hashing
- Admin credentials stored in Supabase `admin_users` table
- Secure password verification

## Environment Variables

You can now remove these from your `.env.local` (they're no longer used):
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`

Admin credentials are now managed in the Supabase database.

