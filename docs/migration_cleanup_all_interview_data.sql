-- Migration: Cleanup ALL interview-related data (including bookings)
-- Run this in Supabase SQL Editor to delete ALL interview data
-- 
-- WARNING: This will permanently delete:
-- - All interview transcripts
-- - All interview evaluations  
-- - All interview bookings
-- - All related data
-- 
-- This is a complete reset. Use only if you want to start completely fresh!

-- ============================================
-- Step 1: Delete evaluation-related data first
-- (due to foreign key constraints)
-- ============================================

-- Delete round evaluations
DELETE FROM interview_round_evaluations;

-- Delete evaluations
DELETE FROM interview_evaluations;

-- Delete transcripts
DELETE FROM interview_transcripts;

-- ============================================
-- Step 2: Delete interview bookings
-- ============================================
-- Note: This will also cascade delete related data due to foreign keys
DELETE FROM interview_bookings;

-- ============================================
-- Step 3: Verify deletion
-- ============================================
-- Uncomment to check:
/*
SELECT 
    'interview_bookings' AS table_name,
    COUNT(*) AS remaining_rows
FROM interview_bookings
UNION ALL
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
