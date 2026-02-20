-- Migration to fix missing 'status' column in interview_bookings
-- Run this in Supabase SQL Editor

-- 1. Create interview_bookings table if it doesn't exist (as a fallback)
CREATE TABLE IF NOT EXISTS interview_bookings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    token TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
    application_text TEXT,
    application_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Add missing columns to interview_bookings
ALTER TABLE interview_bookings ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'completed', 'cancelled', 'failed'));
ALTER TABLE interview_bookings ADD COLUMN IF NOT EXISTS slot_id UUID REFERENCES interview_slots(id) ON DELETE SET NULL;
ALTER TABLE interview_bookings ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES enrolled_users(id) ON DELETE SET NULL;
ALTER TABLE interview_bookings ADD COLUMN IF NOT EXISTS assignment_id UUID REFERENCES user_slot_assignments(id) ON DELETE SET NULL;
ALTER TABLE interview_bookings ADD COLUMN IF NOT EXISTS application_form_id UUID REFERENCES application_forms(id) ON DELETE SET NULL;

-- 3. Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_bookings_token ON interview_bookings(token);
CREATE INDEX IF NOT EXISTS idx_bookings_email ON interview_bookings(email);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON interview_bookings(status);
CREATE INDEX IF NOT EXISTS idx_bookings_slot_id ON interview_bookings(slot_id);
CREATE INDEX IF NOT EXISTS idx_bookings_user_id ON interview_bookings(user_id);
