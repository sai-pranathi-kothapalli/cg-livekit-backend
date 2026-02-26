-- Migration: Store duration_minutes as DOUBLE PRECISION (float) in slots table
-- Run this in Supabase SQL Editor if you want the DB to return float consistently.
-- The agent code coerces to int everywhere, so INTEGER or DOUBLE PRECISION both work.

-- Option A: If your table is named "slots" (Supabase public.slots)
ALTER TABLE slots
  ALTER COLUMN duration_minutes TYPE DOUBLE PRECISION
  USING COALESCE(duration_minutes, 30)::double precision;

COMMENT ON COLUMN slots.duration_minutes IS 'Interview duration in minutes (stored as float; agent uses whole minutes)';

-- Option B: If your table is named "interview_slots", uncomment below and comment Option A:
-- ALTER TABLE interview_slots
--   ALTER COLUMN duration_minutes TYPE DOUBLE PRECISION
--   USING COALESCE(duration_minutes, 30)::double precision;
-- COMMENT ON COLUMN interview_slots.duration_minutes IS 'Interview duration in minutes (stored as float; agent uses whole minutes)';
