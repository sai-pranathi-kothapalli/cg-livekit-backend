# Timezone Fix - IST (Indian Standard Time)

## Problem
When creating interview slots with Indian time, they were being stored or displayed as GMT/UTC time, causing confusion and incorrect scheduling.

## Solution
All datetime operations now consistently use IST (Indian Standard Time, UTC+5:30) throughout the system.

## Changes Made

### 1. **Backend - Slot Creation** ✅
- **File**: `app/api/main.py` - `create_slot` endpoint
- **Fix**: Parse incoming datetime and convert to IST using `to_ist()`
- **Result**: All slots are stored with IST timezone

### 2. **Backend - Slot Service** ✅
- **File**: `app/services/slot_service.py`
- **Fix**: 
  - `create_slot()`: Ensures `start_time` and `end_time` are converted to IST before storing
  - `get_slot()`: Converts retrieved datetimes to IST
  - `get_all_slots()`: Converts all slot datetimes to IST
  - Added `_convert_slot_to_ist()` helper method

### 3. **Backend - Create Day Slots** ✅
- **File**: `app/api/main.py` - `create_day_slots` endpoint
- **Fix**: Creates datetimes with IST timezone explicitly (`replace(tzinfo=IST)`)
- **Result**: Bulk slot creation uses IST timezone

### 4. **Backend - Slot Update** ✅
- **File**: `app/api/main.py` - `update_slot` endpoint
- **Fix**: Converts updated datetime to IST before storing

### 5. **Frontend - Time Display** ✅
- **File**: `Livekit-Frontend/src/pages/AdminManageSlots.tsx`
- **Fix**: Updated `formatTime()` to extract time directly from ISO string and display with "IST" label
- **Result**: Times are displayed in IST without browser timezone conversion

## How It Works

### Backend Flow

1. **Slot Creation**:
   ```
   Admin provides: "2026-01-13T09:00:00" (assumed IST)
   ↓
   Backend parses: datetime.fromisoformat()
   ↓
   Converts to IST: to_ist(datetime)
   ↓
   Stores: "2026-01-13T09:00:00+05:30" (IST with timezone)
   ```

2. **Slot Retrieval**:
   ```
   Database returns: "2026-01-13T09:00:00+05:30"
   ↓
   Backend converts: _convert_slot_to_ist()
   ↓
   API returns: "2026-01-13T09:00:00+05:30" (IST)
   ```

3. **Frontend Display**:
   ```
   Receives: "2026-01-13T09:00:00+05:30"
   ↓
   Extracts time: "09:00"
   ↓
   Formats: "9:00 AM IST"
   ```

## IST Timezone Definition

```python
# app/utils/datetime_utils.py
IST = timezone(timedelta(hours=5, minutes=30))

def to_ist(dt: datetime) -> datetime:
    """Convert an aware datetime to IST or localize a naive one"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)
    return dt.astimezone(IST)
```

## Testing

### Test Scenarios

1. **Create Single Slot**:
   - Input: "2026-01-13T09:00:00"
   - Expected: Stored as "2026-01-13T09:00:00+05:30"
   - Display: "9:00 AM IST"

2. **Create Day Slots**:
   - Input: Date "2026-01-13", Start "09:00", End "17:00"
   - Expected: All slots created with IST timezone
   - Display: Times shown in IST

3. **Retrieve Slots**:
   - Database: "2026-01-13T09:00:00+05:30"
   - API Response: "2026-01-13T09:00:00+05:30"
   - Frontend Display: "9:00 AM IST"

## Benefits

✅ **Consistency**: All times use IST timezone
✅ **Accuracy**: No timezone conversion errors
✅ **Clarity**: Times displayed with "IST" label
✅ **Reliability**: Backend enforces IST, frontend displays IST

## Migration Notes

- Existing slots in database may have UTC/GMT times
- New slots will be created with IST timezone
- When retrieving old slots, they will be converted to IST for display
- Consider migrating existing slots to IST if needed

## Future Improvements

- Add timezone selector (if needed for other regions)
- Validate timezone in frontend before submission
- Show timezone in all datetime inputs
