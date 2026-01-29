-- Verification Queries for Evaluation Tables
-- Run these in Supabase SQL Editor to verify tables were created correctly

-- ============================================
-- 1. Check if all tables exist
-- ============================================
SELECT 
    table_name,
    table_type
FROM information_schema.tables
WHERE table_schema = 'public'
    AND table_name IN (
        'interview_transcripts',
        'interview_evaluations',
        'interview_round_evaluations'
    )
ORDER BY table_name;

-- Expected output: 3 rows showing all three tables

-- ============================================
-- 2. Check table structures
-- ============================================

-- Check interview_transcripts columns
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'interview_transcripts'
ORDER BY ordinal_position;

-- Check interview_evaluations columns
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'interview_evaluations'
ORDER BY ordinal_position;

-- Check interview_round_evaluations columns
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'interview_round_evaluations'
ORDER BY ordinal_position;

-- ============================================
-- 3. Check indexes
-- ============================================
SELECT 
    indexname,
    tablename,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
    AND tablename IN (
        'interview_transcripts',
        'interview_evaluations',
        'interview_round_evaluations'
    )
ORDER BY tablename, indexname;

-- ============================================
-- 4. Check foreign key constraints
-- ============================================
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_name IN (
        'interview_transcripts',
        'interview_evaluations',
        'interview_round_evaluations'
    )
ORDER BY tc.table_name;

-- ============================================
-- 5. Check trigger function
-- ============================================
SELECT 
    trigger_name,
    event_manipulation,
    event_object_table,
    action_statement
FROM information_schema.triggers
WHERE trigger_schema = 'public'
    AND event_object_table = 'interview_evaluations';

-- ============================================
-- 6. Test insert (optional - will create test data)
-- ============================================
-- Uncomment to test inserting data (requires an existing booking token)

/*
-- First, get a booking token to test with
SELECT token FROM interview_bookings LIMIT 1;

-- Then test insert (replace 'YOUR_BOOKING_TOKEN' with actual token)
INSERT INTO interview_transcripts (
    booking_token,
    room_name,
    message_role,
    message_content,
    message_index
) VALUES (
    'YOUR_BOOKING_TOKEN',
    'test_room',
    'assistant',
    'Test message',
    0
) RETURNING id, booking_token, message_role;

-- Clean up test data
DELETE FROM interview_transcripts WHERE room_name = 'test_room';
*/

-- ============================================
-- 7. Quick summary check
-- ============================================
SELECT 
    'interview_transcripts' AS table_name,
    COUNT(*) AS row_count
FROM interview_transcripts
UNION ALL
SELECT 
    'interview_evaluations' AS table_name,
    COUNT(*) AS row_count
FROM interview_evaluations
UNION ALL
SELECT 
    'interview_round_evaluations' AS table_name,
    COUNT(*) AS row_count
FROM interview_round_evaluations;

-- Expected: All tables should show 0 rows initially (empty tables are fine)
