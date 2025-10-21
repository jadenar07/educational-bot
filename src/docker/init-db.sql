CREATE SCHEMA profiles;
CREATE TYPE user_role AS ENUM ('admin', 'ta', 'professor', 'student');
CREATE TABLE profiles.users(
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    role user_role NOT NULL,
    default_collection VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
-- New table soon for queries, and userqueries(6) should ref this table. 