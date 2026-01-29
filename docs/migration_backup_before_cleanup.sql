-- Migration: Backup interview data before cleanup
-- Run this BEFORE running cleanup scripts to create backups
-- 
-- This creates backup tables with all current data

-- ============================================
-- 1. Backup interview transcripts
-- ============================================
CREATE TABLE IF NOT EXISTS interview_transcripts_backup AS 
SELECT * FROM interview_transcripts;

-- ============================================
-- 2. Backup interview evaluations
-- ============================================
CREATE TABLE IF NOT EXISTS interview_evaluations_backup AS 
SELECT * FROM interview_evaluations;

-- ============================================
-- 3. Backup interview round evaluations
-- ============================================
CREATE TABLE IF NOT EXISTS interview_round_evaluations_backup AS 
SELECT * FROM interview_round_evaluations;

-- ============================================
-- 4. Backup interview bookings (optional)
-- ============================================
CREATE TABLE IF NOT EXISTS interview_bookings_backup AS 
SELECT * FROM interview_bookings;

-- ============================================
-- Verify backups
-- ============================================
SELECT 
    'interview_transcripts_backup' AS backup_table,
    COUNT(*) AS row_count
FROM interview_transcripts_backup
UNION ALL
SELECT 
    'interview_evaluations_backup' AS backup_table,
    COUNT(*) AS row_count
FROM interview_evaluations_backup
UNION ALL
SELECT 
    'interview_round_evaluations_backup' AS backup_table,
    COUNT(*) AS row_count
FROM interview_round_evaluations_backup
UNION ALL
SELECT 
    'interview_bookings_backup' AS backup_table,
    COUNT(*) AS row_count
FROM interview_bookings_backup;

-- ============================================
-- To restore from backup later (if needed):
-- ============================================
/*
INSERT INTO interview_transcripts 
SELECT * FROM interview_transcripts_backup;

INSERT INTO interview_evaluations 
SELECT * FROM interview_evaluations_backup;

INSERT INTO interview_round_evaluations 
SELECT * FROM interview_round_evaluations_backup;

INSERT INTO interview_bookings 
SELECT * FROM interview_bookings_backup;
*/
