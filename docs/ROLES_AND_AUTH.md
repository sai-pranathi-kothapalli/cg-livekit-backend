# Roles and how they are handled

Roles are **not stored as a field** in the database. They are **derived from which collection** the user belongs to and are put into the **JWT** at login. Access control then uses the JWT `role`.

## Two kinds of “users”

| Type | Collection | Used for | Role |
|------|------------|----------|------|
| **Admin** | `admin_users` | Login (username + password). Seeded via `seed_admin.py`. | `admin` |
| **Student** | `students` | Login (email + password). Created when you enroll a user. | `student` |
| **Enrolled user** | `enrolled_users` | Profile + slot assignments. **Not** a login account; no role. | — |

So:

- **Admin** → stored in `admin_users`, no `role` field in DB; role is always `admin` at login.
- **Student** → stored in `students`, no `role` field in DB; role is always `student` at login.
- **Enrolled user** → stored in `enrolled_users`; no login, no role. The **same person** has a login as a **student** (same email in `students`).

## Where the role is set

1. **Login** (`POST /api/auth/login`)
   - If auth succeeds against `admin_users` → API returns JWT with `role: 'admin'` and user object includes `role: 'admin'`.
   - If auth succeeds against `students` → API returns JWT with `role: 'student'` and user object includes `role: 'student'`.
2. **JWT payload** (from `auth_service.generate_token`) always includes:
   - `user_id`, `role`, `exp`, `iat`, and optionally `email` / `username`.
3. **Auth dependencies** (`app/utils/auth_dependencies.py`):
   - Read `role` from the JWT.
   - `get_current_user`: loads user from DB by `role` — if `admin` → `auth_service.get_admin_by_id`, if `student` → `auth_service.get_student_by_id`.
   - `get_current_admin`: requires `current_user['role'] == 'admin'`.
   - `get_current_student`: requires `current_user['role'] == 'student'`.

So the **role is only in the JWT and in the in-memory user object** returned by auth; it is **not** stored in MongoDB.

## When you “create user” (enroll user)

`POST /api/admin/users` (enroll user) does two things:

1. **Creates a student (login account)** in `students` with a temporary password (so they can log in).  
   When they log in, they are treated as **role `student`** (from `students`).
2. **Creates an enrolled user** in `enrolled_users` (name, email, phone, notes, slot assignments).  
   This record has **no role**; it’s just profile + assignments.

So “created user” gets:

- A **student** account → role `student` when they log in.
- An **enrolled_user** record → no role, used for admin UI and slot assignment.

## Summary

| Question | Answer |
|----------|--------|
| Where is the role stored? | Not in the DB. It is set at login from the collection (`admin_users` → admin, `students` → student) and stored in the JWT and in the user object returned to the client. |
| How are roles handled? | Login puts `role` in the JWT; `get_current_user` uses that role to load the right user from `admin_users` or `students`; `get_current_admin` / `get_current_student` enforce admin-only or student-only routes. |
| Does `enrolled_users` have a role? | No. Enrolled users are candidates; their login identity is in `students` with role `student`. |
