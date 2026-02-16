from datetime import datetime, timezone, timedelta
import re
from fastapi import HTTPException, status

# Indian Standard Time (IST) offset: UTC +5:30
IST = timezone(timedelta(hours=5, minutes=30))

def get_now_ist() -> datetime:
    """Get current datetime in IST"""
    return datetime.now(IST)

def format_iso_ist(dt: datetime) -> str:
    """Format datetime as ISO string with IST offset"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt.isoformat()

def to_ist(dt: datetime) -> datetime:
    """Convert an aware datetime to IST or localize a naive one"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)
    return dt.astimezone(IST)

def parse_datetime_safe(dt_str: str) -> datetime:
    """
    Parse a datetime string that could be in UTC or IST format.
    Handles:
    - UTC format: '2026-01-28T12:24:00Z' or '2026-01-28T12:24:00+00:00'
    - IST format: '2026-01-28T12:24:00+05:30'
    - Naive format: '2026-01-28T12:24:00' (assumed IST)
    
    Always returns IST-aware datetime.
    
    IMPORTANT: Supabase typically stores timestamps in UTC and may return them
    in UTC format even if we stored them with IST timezone. This function
    properly handles both cases.
    """
    if not dt_str:
        raise ValueError("Empty datetime string")
    
    # Remove any whitespace
    dt_str = dt_str.strip()
    
    # Check if it's UTC (Z or +00:00 or -00:00)
    # Check for Z at the end or +00:00/-00:00 anywhere in the string
    is_utc = False
    if dt_str.endswith('Z'):
        is_utc = True
        dt_str_clean = dt_str.replace('Z', '+00:00')
    elif dt_str.endswith('+00:00') or dt_str.endswith('-00:00'):
        is_utc = True
        dt_str_clean = dt_str
    elif '+00:00' in dt_str or '-00:00' in dt_str:
        # UTC timezone somewhere in the string
        is_utc = True
        dt_str_clean = dt_str
    
    if is_utc:
        # It's UTC - parse and convert to IST
        try:
            # Python < 3.11 fromisoformat is strict about microsecond length (expects 3 or 6)
            # Supabase sometimes returns 5 or other counts.
            if '.' in dt_str_clean:
                base, resto = dt_str_clean.split('.', 1)
                # resto might be '16726+00:00'
                if '+' in resto:
                    ms_part, tz_part = resto.split('+', 1)
                    tz_part = '+' + tz_part
                elif '-' in resto:
                    ms_part, tz_part = resto.split('-', 1)
                    tz_part = '-' + tz_part
                else:
                    ms_part, tz_part = resto, ""
                
                # Normalize ms_part to 6 digits
                ms_part = (ms_part + "000000")[:6]
                dt_str_clean = f"{base}.{ms_part}{tz_part}"

            dt = datetime.fromisoformat(dt_str_clean)
            # Ensure it's UTC-aware, then convert to IST
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(IST)
        except ValueError as e:
            raise ValueError(f"Failed to parse UTC datetime '{dt_str}': {e}")
    
    # Check if it already has IST timezone
    if '+05:30' in dt_str:
        # Already in IST format
        try:
            dt = datetime.fromisoformat(dt_str)
            return to_ist(dt)
        except ValueError as e:
            raise ValueError(f"Failed to parse IST datetime '{dt_str}': {e}")
    
    # Try parsing as-is (might have other timezone or be naive)
    try:
        dt = datetime.fromisoformat(dt_str)
        # If naive, assume IST; if aware, convert to IST
        return to_ist(dt)
    except ValueError:
        # Fallback: try removing any timezone indicators and assume IST
        dt_str_clean = dt_str.replace('Z', '').replace('+00:00', '').replace('-00:00', '')
        # Remove any other timezone patterns
        dt_str_clean = re.sub(r'[+-]\d{2}:\d{2}$', '', dt_str_clean)
        try:
            dt = datetime.fromisoformat(dt_str_clean)
            return dt.replace(tzinfo=IST)
        except ValueError as e:
            raise ValueError(f"Failed to parse datetime '{dt_str}' even after cleanup: {e}")

def validate_scheduled_time(scheduled_at: datetime) -> None:
    """
    Validate that scheduled time is at least 5 minutes in the future.
    
    Args:
        scheduled_at: Scheduled datetime to validate
        
    Raises:
        HTTPException: If scheduled time is invalid
    """
    now = get_now_ist()
    five_minutes_from_now = now + timedelta(minutes=5)
    
    if scheduled_at <= five_minutes_from_now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scheduled time must be at least 5 minutes from now"
        )
