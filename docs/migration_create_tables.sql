-- Migration: Create tables for job descriptions and admin users
-- Run this in Supabase SQL Editor

-- ============================================
-- 1. Job Descriptions Table
-- ============================================
CREATE TABLE IF NOT EXISTS job_descriptions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    requirements TEXT NOT NULL,
    preparation_areas JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create a single row for job description (we'll always update this one)
INSERT INTO job_descriptions (id, title, description, requirements, preparation_areas)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Professional Interview',
    'We are conducting interviews for qualified candidates. This is an opportunity to demonstrate your skills, experience, and suitability for the role.',
    'Relevant qualifications and experience. Good communication skills. Computer literacy.',
    '["Personal Introduction: Your background, education, and motivation", "Technical Knowledge: Domain expertise and relevant skills", "Problem Solving: Scenarios and practical thinking", "Domain Knowledge: Fundamentals and industry awareness"]'::jsonb
)
ON CONFLICT (id) DO NOTHING;

-- ============================================
-- 2. Admin Users Table
-- ============================================
CREATE TABLE IF NOT EXISTS admin_users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create default admin user (username: admin, password: Admin@123)
-- Password hash for 'Admin@123' using bcrypt
-- To generate a new hash, use: python -c "import bcrypt; print(bcrypt.hashpw('your_password'.encode(), bcrypt.gensalt()).decode())"
INSERT INTO admin_users (username, password_hash)
VALUES (
    'admin',
    '$2b$12$jtha/dFempx8J0bk.BxsOeYcE4CocbhoC.0d6eBRW9xzLZiX/8Z..'  -- bcrypt hash for 'Admin@123'
)
ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash;

-- ============================================
-- 3. Enable Row Level Security (Optional)
-- ============================================
-- ALTER TABLE job_descriptions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE admin_users ENABLE ROW LEVEL SECURITY;

-- ============================================
-- 3. Students Table
-- ============================================
CREATE TABLE IF NOT EXISTS students (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    phone TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_students_email ON students(email);

-- ============================================
-- 4. Enrolled Users Table (for admin to manage users)
-- ============================================
CREATE TABLE IF NOT EXISTS enrolled_users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    status TEXT DEFAULT 'enrolled' CHECK (status IN ('enrolled', 'interviewed', 'selected', 'rejected')),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_enrolled_users_email ON enrolled_users(email);
CREATE INDEX IF NOT EXISTS idx_enrolled_users_status ON enrolled_users(status);

-- ============================================
-- 5. Create Indexes
-- ============================================
CREATE INDEX IF NOT EXISTS idx_admin_users_username ON admin_users(username);

