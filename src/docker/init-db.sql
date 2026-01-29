CREATE SCHEMA IF NOT EXISTS profiles;

DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('admin', 'ta', 'professor', 'student');
EXCEPTION WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS profiles.users(
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    role user_role NOT NULL,
    default_collection VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_email ON profiles.users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON profiles.users(username);