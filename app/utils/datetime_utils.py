from datetime import datetime, timezone, timedelta

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
