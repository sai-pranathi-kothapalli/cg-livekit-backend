-- User Slot Assignments Table
-- Tracks which slots are assigned to which users during enrollment

CREATE TABLE IF NOT EXISTS user_slot_assignments (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES enrolled_users(id) ON DELETE CASCADE,
    slot_id UUID NOT NULL REFERENCES interview_slots(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'assigned' CHECK (status IN ('assigned', 'selected', 'cancelled')),
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    selected_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, slot_id) -- A user can only have one assignment per slot
);

CREATE INDEX IF NOT EXISTS idx_assignments_user_id ON user_slot_assignments(user_id);
CREATE INDEX IF NOT EXISTS idx_assignments_slot_id ON user_slot_assignments(slot_id);
CREATE INDEX IF NOT EXISTS idx_assignments_status ON user_slot_assignments(status);
CREATE INDEX IF NOT EXISTS idx_assignments_user_status ON user_slot_assignments(user_id, status);

-- Update enrolled_users table to track interview status
ALTER TABLE enrolled_users ADD COLUMN IF NOT EXISTS interview_status TEXT DEFAULT 'enrolled' CHECK (interview_status IN ('enrolled', 'slot_selected', 'scheduled', 'completed', 'cancelled'));

CREATE INDEX IF NOT EXISTS idx_enrolled_users_interview_status ON enrolled_users(interview_status);

-- Update interview_bookings to link with user_slot_assignments
ALTER TABLE interview_bookings ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES enrolled_users(id) ON DELETE SET NULL;
ALTER TABLE interview_bookings ADD COLUMN IF NOT EXISTS assignment_id UUID REFERENCES user_slot_assignments(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_bookings_user_id ON interview_bookings(user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_assignment_id ON interview_bookings(assignment_id);

