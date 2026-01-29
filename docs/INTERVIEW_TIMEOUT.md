# Interview Time-Based Termination & Auto-Redirect

## Overview

The interview system now automatically terminates interviews when the scheduled time limit is reached and redirects users to the evaluation page.

## How It Works

### 1. **Time Limit Detection**

The system determines interview duration from:
- **Slot Duration** (if booking has `slot_id`): Uses `end_time - start_time` from the slot
- **Default Duration**: 30 minutes if no slot information available
- **Scheduled End Time**: Calculated as `scheduled_at + duration`

### 2. **Time Monitoring**

During the interview loop:
- Checks every 5 seconds if time limit has been reached
- Calculates time remaining
- Sends 2-minute warning before end
- Automatically terminates when limit reached

### 3. **Graceful Termination**

When time limit is reached:
1. Agent generates closing message ("Thank you, interview complete")
2. Sends completion signal to frontend via data channel
3. Updates booking status to "completed"
4. Waits 3 seconds for final data to be saved
5. Frontend automatically redirects to evaluation page

### 4. **Frontend Auto-Redirect**

- Listens for `interview_completed` signal on data channel
- Extracts token from signal or uses current interview token
- Redirects to `/evaluation/{token}` after 3-second delay
- Shows completion message during delay

## Configuration

### Default Duration
- **Default**: 30 minutes
- **Slot-based**: Uses slot's `end_time - start_time` if available
- **Configurable**: Can be adjusted per slot (30 or 45 minutes)

### Time Warning
- **Warning sent**: 2 minutes before time limit
- **Message**: "Interview will end in approximately X minute(s). Please wrap up your responses."

## Data Flow

```
Interview Starts
    ↓
Time monitoring loop (every 5 seconds)
    ↓
2 minutes remaining → Send warning
    ↓
Time limit reached → Generate closing message
    ↓
Send completion signal to frontend
    ↓
Update booking status to "completed"
    ↓
Create evaluation (Step 7)
    ↓
Frontend receives signal → Redirect to /evaluation/{token}
```

## Signals Sent

### 1. Warning Signal (2 min before end)
```json
{
  "type": "interview_warning",
  "message": "Interview will end in approximately 2 minute(s)..."
}
```

### 2. Completion Signal
```json
{
  "type": "interview_completed",
  "message": "Interview completed. Redirecting to evaluation page...",
  "token": "booking_token_here",
  "duration_minutes": 30
}
```

## Benefits

✅ **Automatic Management**: No manual intervention needed
✅ **Consistent Duration**: All interviews respect time limits
✅ **User Experience**: Smooth transition to evaluation
✅ **Data Integrity**: Ensures evaluation is created before redirect
✅ **Professional**: Agent closes interview gracefully

## Testing

To test:
1. Schedule an interview (30 or 45 min slot)
2. Start interview
3. Wait for time limit (or reduce duration for testing)
4. Verify:
   - Warning appears at 2 minutes
   - Closing message is spoken
   - Auto-redirect to evaluation page
   - Evaluation data is available

## Notes

- Time limit is enforced server-side (agent worker)
- Frontend redirect is automatic (no user action needed)
- Evaluation is created immediately after interview ends
- Booking status updated to "completed" automatically
