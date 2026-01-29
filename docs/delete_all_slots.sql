-- SQL Query to Delete All Interview Slots
-- Run this in Supabase SQL Editor
-- WARNING: This will delete ALL slots and cannot be undone!

-- Option 1: Delete all slots (recommended - handles foreign key constraints)
-- This will also set slot_id to NULL in interview_bookings (if ON DELETE SET NULL is configured)
DELETE FROM interview_slots;

-- Option 2: If you want to delete slots and also delete related bookings
-- WARNING: This will delete all bookings associated with slots!
-- DELETE FROM interview_bookings WHERE slot_id IS NOT NULL;
-- DELETE FROM interview_slots;

-- Option 3: If you want to keep bookings but just remove slot references
-- UPDATE interview_bookings SET slot_id = NULL WHERE slot_id IS NOT NULL;
-- DELETE FROM interview_slots;

-- Option 4: Delete slots for a specific date range (safer option)
-- DELETE FROM interview_slots 
-- WHERE slot_datetime >= '2026-01-28 00:00:00' 
--   AND slot_datetime < '2026-01-29 00:00:00';

-- Verify deletion (check how many slots remain)
-- SELECT COUNT(*) FROM interview_slots;

-- Check if any bookings still reference slots (should be 0 or NULL after deletion)
-- SELECT COUNT(*) FROM interview_bookings WHERE slot_id IS NOT NULL;
