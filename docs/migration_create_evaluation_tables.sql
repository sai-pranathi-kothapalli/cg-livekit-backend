-- Migration: Create tables for interview transcripts and evaluations
-- Run this in Supabase SQL Editor

-- ============================================
-- 1. Interview Transcripts Table
-- ============================================
CREATE TABLE IF NOT EXISTS interview_transcripts (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    booking_token TEXT NOT NULL REFERENCES interview_bookings(token) ON DELETE CASCADE,
    room_name TEXT, -- LiveKit room name (session identifier)
    message_role TEXT NOT NULL CHECK (message_role IN ('user', 'assistant', 'system')),
    message_content TEXT NOT NULL,
    message_index INTEGER NOT NULL, -- Order of message in conversation
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transcripts_booking_token ON interview_transcripts(booking_token);
CREATE INDEX IF NOT EXISTS idx_transcripts_room_name ON interview_transcripts(room_name);
CREATE INDEX IF NOT EXISTS idx_transcripts_timestamp ON interview_transcripts(timestamp);

-- ============================================
-- 2. Interview Evaluations Table
-- ============================================
CREATE TABLE IF NOT EXISTS interview_evaluations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    booking_token TEXT UNIQUE NOT NULL REFERENCES interview_bookings(token) ON DELETE CASCADE,
    room_name TEXT, -- LiveKit room name (session identifier)
    
    -- Overall Metrics
    duration_minutes INTEGER,
    total_questions INTEGER DEFAULT 0,
    rounds_completed INTEGER DEFAULT 0,
    overall_score DECIMAL(3,1), -- Score out of 10
    
    -- Round-by-Round Data (stored as JSONB for flexibility)
    rounds_data JSONB DEFAULT '[]'::jsonb, -- Array of round evaluations
    
    -- Evaluation Summary
    strengths JSONB DEFAULT '[]'::jsonb, -- Array of strengths
    areas_for_improvement JSONB DEFAULT '[]'::jsonb, -- Array of improvement areas
    
    -- Interview State Data
    interview_state JSONB, -- Full interview state snapshot
    
    -- Metadata
    evaluated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evaluations_booking_token ON interview_evaluations(booking_token);
CREATE INDEX IF NOT EXISTS idx_evaluations_room_name ON interview_evaluations(room_name);
CREATE INDEX IF NOT EXISTS idx_evaluations_overall_score ON interview_evaluations(overall_score);

-- ============================================
-- 3. Interview Round Evaluations (Detailed breakdown)
-- ============================================
CREATE TABLE IF NOT EXISTS interview_round_evaluations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    evaluation_id UUID NOT NULL REFERENCES interview_evaluations(id) ON DELETE CASCADE,
    round_number INTEGER NOT NULL CHECK (round_number BETWEEN 1 AND 5),
    round_name TEXT NOT NULL,
    
    -- Metrics
    questions_asked INTEGER DEFAULT 0,
    average_rating DECIMAL(3,1), -- Average rating for this round
    time_spent_minutes DECIMAL(5,2),
    time_target_minutes INTEGER,
    
    -- Performance Data
    topics_covered JSONB DEFAULT '[]'::jsonb, -- Array of topics
    performance_summary TEXT,
    response_ratings JSONB DEFAULT '[]'::jsonb, -- Array of individual response ratings
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_round_evaluations_evaluation_id ON interview_round_evaluations(evaluation_id);
CREATE INDEX IF NOT EXISTS idx_round_evaluations_round_number ON interview_round_evaluations(round_number);

-- ============================================
-- 4. Function to update updated_at timestamp
-- ============================================
CREATE OR REPLACE FUNCTION update_evaluation_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for updating updated_at
DROP TRIGGER IF EXISTS update_interview_evaluations_updated_at ON interview_evaluations;
CREATE TRIGGER update_interview_evaluations_updated_at
    BEFORE UPDATE ON interview_evaluations
    FOR EACH ROW
    EXECUTE FUNCTION update_evaluation_updated_at();

-- ============================================
-- 5. Comments for documentation
-- ============================================
COMMENT ON TABLE interview_transcripts IS 'Stores complete conversation history for each interview';
COMMENT ON TABLE interview_evaluations IS 'Stores overall evaluation metrics and summary for each interview';
COMMENT ON TABLE interview_round_evaluations IS 'Stores detailed round-by-round evaluation breakdown';
