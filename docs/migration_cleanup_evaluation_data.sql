-- Migration: Cleanup existing interview evaluation data
-- Run this in Supabase SQL Editor to delete all existing transcripts and evaluations
-- 
-- WARNING: This will permanently delete all interview transcripts and evaluations!
-- Make sure you want to start fresh before running this.

-- ============================================
-- 1. Delete all interview round evaluations
-- ============================================
DELETE FROM interview_round_evaluations;

-- ============================================
-- 2. Delete all interview evaluations
-- ============================================
DELETE FROM interview_evaluations;

-- ============================================
-- 3. Delete all interview transcripts
-- ============================================
DELETE FROM interview_transcripts;

-- ============================================
-- 4. Verify deletion (optional - run to check)
-- ============================================
-- Uncomment to verify all data is deleted:
/*
SELECT 
    'interview_transcripts' AS table_name,
    COUNT(*) AS remaining_rows
FROM interview_transcripts
UNION ALL
SELECT 
    'interview_evaluations' AS table_name,
    COUNT(*) AS remaining_rows
FROM interview_evaluations
UNION ALL
SELECT 
    'interview_round_evaluations' AS table_name,
    COUNT(*) AS remaining_rows
FROM interview_round_evaluations;
*/

-- Expected result: All counts should be 0

-- ============================================
-- Optional: Reset auto-increment sequences (if using serial IDs)
-- ============================================
-- Note: UUIDs don't need sequence reset, but if you want to reset any sequences:
-- ALTER SEQUENCE IF EXISTS interview_transcripts_id_seq RESTART WITH 1;
-- ALTER SEQUENCE IF EXISTS interview_evaluations_id_seq RESTART WITH 1;
-- ALTER SEQUENCE IF EXISTS interview_round_evaluations_id_seq RESTART WITH 1;
