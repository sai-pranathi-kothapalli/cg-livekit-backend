# MongoDB setup (separate DB and admin first)

The app uses a **single MongoDB database** for all data (admin users, enrolled users, students, slots, bookings, etc.). You can use a dedicated database name so data is separate from other projects.

## 1. Set the database name

In `.env`:

```env
MONGODB_URI=mongodb://user:password@host:27017/
MONGODB_DB_NAME=livekit_interview
```

- If `MONGODB_DB_NAME` is **not** set, the default database name is `interview`.
- The database is **created automatically** the first time data is written (e.g. when you seed the admin).

## 2. Create the admin user first

From the backend directory:

```bash
python3 seed_admin.py
```

This will:

- Use the same `MONGODB_URI` and `MONGODB_DB_NAME` from `.env`
- Create or update the admin user in the `admin_users` collection
- Default credentials: **username** `admin`, **password** `Admin@123`

Run this **before** adding other users so the admin exists in that database.

## 3. Start the backend and add users

Start the backend, then add enrolled users via:

- Admin UI (e.g. user management), or
- API: `POST /api/admin/users` (after logging in as admin)

All users and app data will be stored in the same database (`livekit_interview` or whatever you set in `MONGODB_DB_NAME`).

## Summary

| Step | Action |
|------|--------|
| 1 | Set `MONGODB_DB_NAME` in `.env` (e.g. `livekit_interview`) |
| 2 | Run `python3 seed_admin.py` to create the admin in that DB |
| 3 | Start the backend and add users via UI or API |
