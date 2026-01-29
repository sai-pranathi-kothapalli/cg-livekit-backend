-- Migration: Add duration_minutes, start_time, and end_time columns to interview_slots table
-- This migration adds the necessary columns for proper duration tracking
-- Run this in Supabase SQL Editor

-- Step 1: Add start_time and end_time columns if they don't exist
ALTER TABLE interview_slots 
ADD COLUMN IF NOT EXISTS start_time TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS end_time TIMESTAMP WITH TIME ZONE;

-- Step 2: Populate start_time and end_time from slot_datetime for existing slots
-- If start_time is NULL, use slot_datetime as start_time
UPDATE interview_slots
SET start_time = slot_datetime
WHERE start_time IS NULL AND slot_datetime IS NOT NULL;

-- Step 3: Add duration_minutes column if it doesn't exist
ALTER TABLE interview_slots 
ADD COLUMN IF NOT EXISTS duration_minutes INTEGER;

-- Step 4: Calculate and populate duration_minutes for existing slots
-- Option A: If end_time exists, calculate from start_time and end_time
UPDATE interview_slots
SET duration_minutes = EXTRACT(EPOCH FROM (end_time::timestamp - start_time::timestamp)) / 60
WHERE duration_minutes IS NULL 
  AND start_time IS NOT NULL 
  AND end_time IS NOT NULL;

-- Option B: For slots without end_time, set a default duration (45 minutes)
-- You can adjust this default based on your needs
UPDATE interview_slots
SET duration_minutes = 45
WHERE duration_minutes IS NULL;

-- Step 5: Add comments to the columns
COMMENT ON COLUMN interview_slots.duration_minutes IS 'Interview duration in minutes for this slot';
COMMENT ON COLUMN interview_slots.start_time IS 'Start time of the interview slot';
COMMENT ON COLUMN interview_slots.end_time IS 'End time of the interview slot';

-- Step 6: Verify the migration
-- Run this query to check if columns were added successfully:
-- SELECT column_name, data_type 
-- FROM information_schema.columns 
-- WHERE table_name = 'interview_slots' 
--   AND column_name IN ('duration_minutes', 'start_time', 'end_time');
