import pytest
from datetime import datetime, timezone, timedelta
from app.utils.datetime_utils import (
    IST,
    get_now_ist,
    format_iso_ist,
    to_ist,
    parse_datetime_safe,
    validate_scheduled_time
)
from fastapi import HTTPException

def test_get_now_ist():
    now = get_now_ist()
    assert now.tzinfo == IST

def test_format_iso_ist():
    dt = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    # format_iso_ist should probably convert to IST if the intent is to return an IST string
    formatted = format_iso_ist(to_ist(dt))
    assert "2026-01-01T17:30:00+05:30" in formatted

def test_to_ist():
    # Naive
    dt = datetime(2026, 1, 1, 12, 0, 0)
    ist_dt = to_ist(dt)
    assert ist_dt.tzinfo == IST
    
    # Aware UTC
    utc_dt = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ist_dt = to_ist(utc_dt)
    assert ist_dt.hour == 17
    assert ist_dt.minute == 30

def test_parse_datetime_safe_utc():
    # Z format
    dt_str = "2026-01-28T12:00:00Z"
    dt = parse_datetime_safe(dt_str)
    assert dt.hour == 17
    assert dt.minute == 30
    assert dt.tzinfo == IST
    
    # +00:00 format
    dt_str = "2026-01-28T12:00:00+00:00"
    dt = parse_datetime_safe(dt_str)
    assert dt.hour == 17

def test_parse_datetime_safe_ist():
    dt_str = "2026-01-28T12:00:00+05:30"
    dt = parse_datetime_safe(dt_str)
    assert dt.hour == 12
    assert dt.tzinfo == IST

def test_parse_datetime_safe_naive():
    dt_str = "2026-01-28T12:00:00"
    dt = parse_datetime_safe(dt_str)
    assert dt.hour == 12
    assert dt.tzinfo == IST

def test_parse_datetime_safe_microsecond_normalize():
    # 5 digit microsecond (Supabase quirk)
    dt_str = "2026-01-28T12:00:00.12345Z"
    dt = parse_datetime_safe(dt_str)
    assert dt.microsecond == 123450

def test_validate_scheduled_time_fail():
    past_time = get_now_ist() - timedelta(minutes=1)
    with pytest.raises(HTTPException) as excinfo:
        validate_scheduled_time(past_time)
    assert excinfo.value.status_code == 400

def test_validate_scheduled_time_success():
    future_time = get_now_ist() + timedelta(minutes=10)
    # Should not raise
    validate_scheduled_time(future_time)
