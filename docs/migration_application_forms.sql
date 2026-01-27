-- Student Application Forms Table
-- Stores application forms filled/uploaded by students

CREATE TABLE IF NOT EXISTS student_application_forms (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES enrolled_users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'submitted', 'verified', 'rejected')),
    
    -- Personal Details
    full_name TEXT NOT NULL,
    post TEXT,
    category TEXT,
    date_of_birth DATE,
    gender TEXT,
    marital_status TEXT,
    aadhaar_number TEXT,
    pan_number TEXT,
    father_name TEXT,
    mother_name TEXT,
    spouse_name TEXT,
    
    -- Address Details
    correspondence_address1 TEXT,
    correspondence_address2 TEXT,
    correspondence_address3 TEXT,
    correspondence_state TEXT,
    correspondence_district TEXT,
    correspondence_pincode TEXT,
    permanent_address1 TEXT,
    permanent_address2 TEXT,
    permanent_address3 TEXT,
    permanent_state TEXT,
    permanent_district TEXT,
    permanent_pincode TEXT,
    
    -- Contact Details
    mobile_number TEXT,
    alternative_number TEXT,
    email TEXT,
    
    -- Educational Qualification
    ssc_board TEXT,
    ssc_passing_date TEXT,
    ssc_percentage TEXT,
    ssc_class TEXT,
    graduation_degree TEXT,
    graduation_college TEXT,
    graduation_specialization TEXT,
    graduation_passing_date TEXT,
    graduation_percentage TEXT,
    graduation_class TEXT,
    
    -- Other Details
    religion TEXT,
    religious_minority BOOLEAN DEFAULT FALSE,
    local_language_studied BOOLEAN DEFAULT FALSE,
    local_language_name TEXT,
    computer_knowledge BOOLEAN DEFAULT FALSE,
    computer_knowledge_details TEXT,
    languages_known JSONB, -- Store as JSON object
    
    -- Application Specific
    state_applying_for TEXT,
    regional_rural_bank TEXT,
    exam_center_preference1 TEXT,
    exam_center_preference2 TEXT,
    medium_of_paper TEXT,
    
    -- File Upload (if uploaded as PDF)
    application_file_url TEXT, -- URL to uploaded PDF file
    application_text TEXT, -- Extracted text from PDF (for AI agent)
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    submitted_at TIMESTAMP WITH TIME ZONE,
    
    UNIQUE(user_id) -- One application form per user
);

CREATE INDEX IF NOT EXISTS idx_application_forms_user_id ON student_application_forms(user_id);
CREATE INDEX IF NOT EXISTS idx_application_forms_status ON student_application_forms(status);

-- Add application_form_id to interview_bookings to link booking with application
ALTER TABLE interview_bookings ADD COLUMN IF NOT EXISTS application_form_id UUID REFERENCES student_application_forms(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_bookings_application_form_id ON interview_bookings(application_form_id);

