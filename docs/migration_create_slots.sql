-- Interview Slots Table
-- This table stores available time slots for interviews

CREATE TABLE IF NOT EXISTS interview_slots (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    slot_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    max_capacity INTEGER NOT NULL DEFAULT 1,  -- Maximum number of interviews in this slot
    current_bookings INTEGER NOT NULL DEFAULT 0,  -- Current number of bookings
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'full', 'cancelled')),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,  -- Admin user who created the slot
    CONSTRAINT check_capacity CHECK (current_bookings <= max_capacity)
);

CREATE INDEX IF NOT EXISTS idx_slots_datetime ON interview_slots(slot_datetime);
CREATE INDEX IF NOT EXISTS idx_slots_status ON interview_slots(status);
CREATE INDEX IF NOT EXISTS idx_slots_status_datetime ON interview_slots(status, slot_datetime);

-- Update interview_bookings table to reference slot_id
ALTER TABLE interview_bookings ADD COLUMN IF NOT EXISTS slot_id UUID REFERENCES interview_slots(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_bookings_slot_id ON interview_bookings(slot_id);

