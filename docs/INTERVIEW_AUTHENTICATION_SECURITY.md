# Interview Authentication & Security

## Overview

Interview link access is **configurable** via `REQUIRE_LOGIN_FOR_INTERVIEW` (backend `.env`):

- **`true`** (default): Only a logged-in student who owns the booking can open the interview link. Same as before.
- **`false`**: Anyone with the link (token) can open and attend the interview without logging in.

Set in backend: `REQUIRE_LOGIN_FOR_INTERVIEW=true` or `false`. The frontend reads this from `GET /api/public/interview-config` and skips the login gate when `false`.

## Security Implementation

### 1. **Backend Authentication Checks**

#### `/api/connection-details` Endpoint
- When `REQUIRE_LOGIN_FOR_INTERVIEW=true`: requires student authentication and verifies booking ownership.
- When `REQUIRE_LOGIN_FOR_INTERVIEW=false`: no auth required; anyone with the token can get connection details.

#### `/api/booking/{token}` Endpoint
- When `REQUIRE_LOGIN_FOR_INTERVIEW=true`: requires student authentication and verifies ownership.
- When `REQUIRE_LOGIN_FOR_INTERVIEW=false`: no auth required; anyone with the token can get booking details.

#### `GET /api/public/interview-config` (no auth)
- Returns `{ require_login_for_interview: boolean }` so the frontend can show or skip the login gate.

### 2. **Frontend Authentication Checks**

#### `InterviewPage` Component
- **Checks**: User authentication status using `useAuth()` hook
- **Requires**: Student role (`isStudent === true`)
- **Redirects**: To login page if not authenticated
- **Shows**: Error message if access denied

#### API Requests
- **Sends**: Authorization header with JWT token
- **Includes**: `Bearer {token}` in all interview-related requests

## Authentication Flow

```
1. User clicks interview link: /interview/{token}
   ↓
2. Frontend checks: Is user logged in? Is user a student?
   ↓
3. If NO → Redirect to /login with redirect state
   ↓
4. If YES → Call /api/booking/{token} with auth token
   ↓
5. Backend verifies:
   - Token is valid
   - User is a student
   - booking.user_id === enrolled_user.id
   ↓
6. If verified → Return booking data
   ↓
7. Frontend calls /api/connection-details with auth token
   ↓
8. Backend verifies ownership again
   ↓
9. If verified → Return LiveKit connection details
   ↓
10. Interview starts
```

## Security Features

### ✅ **Authentication Required**
- No anonymous access to interviews
- Must be logged in as a student

### ✅ **Ownership Verification**
- Backend verifies `booking.user_id === enrolled_user.id`
- Prevents students from accessing other students' interviews

### ✅ **Token-Based Auth**
- JWT tokens in Authorization header
- Tokens validated on every request

### ✅ **Role-Based Access**
- Only students can access interviews
- Admins cannot access student interviews (unless explicitly allowed)

## Error Handling

### Frontend Errors

1. **`authentication_required`**
   - User not logged in
   - Redirects to login page

2. **`access_denied`**
   - User logged in but doesn't own the interview
   - Shows error message

3. **`Interview not found`**
   - Token is invalid or booking doesn't exist
   - Shows error message

### Backend Errors

1. **`401 Unauthorized`**
   - No auth token provided
   - Invalid/expired token
   - Not a student role

2. **`403 Forbidden`**
   - Student authenticated but doesn't own the booking
   - Booking `user_id` doesn't match student's `enrolled_user.id`

3. **`404 Not Found`**
   - Booking doesn't exist
   - Invalid token

## Backward Compatibility

- **Old bookings without `user_id`**: Allowed for backward compatibility
- **Warning logged**: When accessing booking without `user_id`
- **Future**: All new bookings will have `user_id` set

## Testing

### Test Scenarios

1. **Valid Access**:
   - Student logs in
   - Clicks their interview link
   - ✅ Should access interview

2. **Unauthenticated Access**:
   - User not logged in
   - Clicks interview link
   - ❌ Should redirect to login

3. **Wrong Student**:
   - Student A logs in
   - Tries to access Student B's interview
   - ❌ Should show "Access Denied"

4. **Invalid Token**:
   - Student logs in
   - Uses invalid/fake token
   - ❌ Should show "Interview not found"

## Benefits

✅ **Security**: Prevents unauthorized access
✅ **Privacy**: Students can only see their own interviews
✅ **Accountability**: All access is logged and authenticated
✅ **User Experience**: Clear error messages guide users

## Migration Notes

- Existing interviews without `user_id` will still work (backward compatibility)
- New interviews will always have `user_id` set
- All interview access now requires authentication
