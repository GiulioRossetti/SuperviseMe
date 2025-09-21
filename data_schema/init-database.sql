-- SuperviseMe PostgreSQL Database Schema
-- This script creates the database schema for the SuperviseMe application

-- Create user management table
CREATE TABLE IF NOT EXISTS user_mgmt (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    surname VARCHAR(255),
    cdl VARCHAR(255),
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    user_type VARCHAR(50) NOT NULL CHECK (user_type IN ('admin', 'supervisor', 'student')),
    joined_on INTEGER NOT NULL,
    gender VARCHAR(50),
    nationality VARCHAR(100)
);

-- Create thesis table
CREATE TABLE IF NOT EXISTS thesis (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    author_id INTEGER REFERENCES user_mgmt(id) ON DELETE CASCADE,
    frozen BOOLEAN DEFAULT FALSE,
    created_at INTEGER NOT NULL,
    level VARCHAR(20) CHECK (level IN ('bachelor', 'master', 'phd', 'other'))
);

-- Create thesis status tracking table
CREATE TABLE IF NOT EXISTS thesis_status (
    id SERIAL PRIMARY KEY,
    thesis_id INTEGER REFERENCES thesis(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL,
    updated_at INTEGER NOT NULL
);

-- Create thesis-supervisor relationship table
CREATE TABLE IF NOT EXISTS thesis_supervisor (
    id SERIAL PRIMARY KEY,
    thesis_id INTEGER REFERENCES thesis(id) ON DELETE CASCADE,
    supervisor_id INTEGER REFERENCES user_mgmt(id) ON DELETE CASCADE,
    assigned_at INTEGER NOT NULL,
    UNIQUE(thesis_id, supervisor_id)
);

-- Create thesis tags table
CREATE TABLE IF NOT EXISTS thesis_tag (
    id SERIAL PRIMARY KEY,
    thesis_id INTEGER REFERENCES thesis(id) ON DELETE CASCADE,
    tag VARCHAR(100) NOT NULL
);

-- Create thesis updates table
CREATE TABLE IF NOT EXISTS thesis_update (
    id SERIAL PRIMARY KEY,
    thesis_id INTEGER REFERENCES thesis(id) ON DELETE CASCADE,
    author_id INTEGER REFERENCES user_mgmt(id) ON DELETE CASCADE,
    update_type VARCHAR(50) NOT NULL,
    parent_id INTEGER REFERENCES thesis_update(id) ON DELETE CASCADE,
    status VARCHAR(50),
    content TEXT,
    created_at INTEGER NOT NULL
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_user_mgmt_username ON user_mgmt(username);
CREATE INDEX IF NOT EXISTS idx_user_mgmt_email ON user_mgmt(email);
CREATE INDEX IF NOT EXISTS idx_user_mgmt_type ON user_mgmt(user_type);
CREATE INDEX IF NOT EXISTS idx_thesis_author ON thesis(author_id);
CREATE INDEX IF NOT EXISTS idx_thesis_level ON thesis(level);
CREATE INDEX IF NOT EXISTS idx_thesis_status_thesis ON thesis_status(thesis_id);
CREATE INDEX IF NOT EXISTS idx_thesis_supervisor_thesis ON thesis_supervisor(thesis_id);
CREATE INDEX IF NOT EXISTS idx_thesis_supervisor_supervisor ON thesis_supervisor(supervisor_id);
CREATE INDEX IF NOT EXISTS idx_thesis_tag_thesis ON thesis_tag(thesis_id);
CREATE INDEX IF NOT EXISTS idx_thesis_update_thesis ON thesis_update(thesis_id);
CREATE INDEX IF NOT EXISTS idx_thesis_update_author ON thesis_update(author_id);

-- Insert default admin user (will be overridden by application initialization)
INSERT INTO user_mgmt (username, name, surname, email, password, user_type, joined_on)
VALUES (
    'admin',
    'System',
    'Administrator',
    'admin@superviseme.local',
    -- This is a placeholder password that will be replaced by the application
    'pbkdf2:sha256:260000$temp$dummy',
    'admin',
    EXTRACT(epoch FROM now())::INTEGER
) ON CONFLICT (username) DO NOTHING;