# LMS Integration Guide — AI Interview Platform

**For:** LMS Team (Codegnan)  
**Status:** AI Interview Platform is **READY** — all endpoints tested and verified.

## Quick Start
- **Base URL:** `http://<ai-interview-server>:8000`
- **Auth:** Every request needs `X-API-Key` header.
- **API Key:** `cgn_live_lms_a49dfa338a492e21ef0c0e51ce2d4dbfd897bc7628540b35`
- **Swagger Docs:** `http://<server>:8000/docs` → look for the **"Integration"** section.

### Test your key:
```bash
curl -H "X-API-Key: cgn_live_lms_a49dfa338a492e21ef0c0e51ce2d4dbfd897bc7628540b35" http://localhost:8000/api/integration/health
```
**Expected Response:** `{"status": "ok", "authenticated_as": "Codegnan LMS"}`

---

## Complete Flow

### Step 1: Sync students → Enroll in AI Interview
**When:** Manager clicks "Sync Batch" in LMS.  
Your service fetches students from MongoDB and calls:

**POST** `/api/integration/enroll-students`
```json
{
    "batch": "PFS-106",
    "location": "vijayawada",
    "students": [
        {
            "student_id": "5b21f704-280d-4b16-80dc-a69bbbb97cc4",
            "email": "arunanjali@gmail.com",
            "name": "Arunanjali Satyala",
            "batch": "PFS-106",
            "location": "vijayawada"
        }
    ]
}
```

> [!NOTE]
> `student_id` is your UUID from LMS MongoDB. We store it as `external_student_id`. This endpoint is **idempotent**; calling it twice with the same ID will simply return `already_existed`.

---

### Step 2: Schedule interview → Create slots
**When:** Manager clicks "Schedule Interview" in LMS.  
Your service reads curriculum topics from your curriculum table and calls:

**POST** `/api/integration/schedule-interview`
```json
{
    "batch": "PFS-106",
    "location": "vijayawada",
    "date": "2026-04-10",
    "window_start": "09:00",
    "window_end": "21:00",
    "interview_duration": 30,
    "curriculum_topics": "Python: loops, functions; MySQL: SELECT, JOINS",
    "capacity": 30,
    "student_id": "5b21f704-280d-4b16-80dc-a69bbbb97cc4"
}
```

> [!TIP]
> If `student_id` is provided, the slots are associated with that specific student. This is useful for scheduling 1-on-1 interviews or dedicated windows.

---

### Step 3: Fetch available slots
**When:** Student opens the booking page in LMS.  

**GET** `/api/integration/slots?batch=PFS-106`

> [!IMPORTANT]
> Disable slots in your UI where `available == 0` or `status == "full"`.

---

### Step 4: Student books a slot → Get interview link
**When:** Student picks a time slot and clicks "Book".

**POST** `/api/integration/book-slot`
```json
{
    "student_id": "5b21f704-280d-4b16-80dc-a69bbbb97cc4",
    "batch": "PFS-106",
    "slot_id": "a1b2c3d4-..."
}
```
**Response (Success):**
```json
{
    "success": true,
    "interview_link": "http://localhost:3000/interview/Madm9TJrvJ8...",
    "booking_token": "Madm9TJrvJ8...",
    "scheduled_at": "2026-04-10T09:00:00"
}
```

---

### Step 5: Webhook Setup (Recommended)
**When:** You want real-time results pushed to your LMS.

**POST** `/api/integration/register-webhook`
```json
{
    "target_url": "https://lms.codegnan.com/api/webhook",
    "events": ["EVALUATION_COMPLETED"],
    "secret": "your_secret_here"
}
```

---

### Step 6: Polling for results (Alternative)
If you prefer polling or missed a webhook:

**GET** `/api/integration/evaluation/{booking_token}`

---

## Checklist Before Going Live
- [x] API key works (`/health` endpoint)
- [x] Student enrollment verified (Idempotency tested)
- [x] Slot creation verified
- [x] Booking returns valid `interview_link`
- [x] Webhook registration system verified
- [x] **New Fix:** `enrolled_user_id` correctly handled for integration students (no FK constraint issues)
- [x] Error handling for 409 (Full Slot) verified
