-- schema.sql
-- Drop existing database and user if they exist
-- (Use with caution in production environments)
DROP DATABASE IF EXISTS publication_db;
DROP USER IF EXISTS publication_user;

-- Create the database
CREATE DATABASE publication_db;

-- Create the user
CREATE USER publication_user WITH PASSWORD 'project';

-- Connect to the database as postgres user
\c publication_db postgres

-- Grant permissions to the user
GRANT CONNECT ON DATABASE publication_db TO publication_user;
GRANT USAGE ON SCHEMA public TO publication_user;
GRANT CREATE ON SCHEMA public TO publication_user; -- Allow user to create tables

-- Grant specific table privileges for better security and maintenance
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO publication_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO publication_user;

-- Create authors table
CREATE TABLE authors (
    author_id SERIAL PRIMARY KEY,
    author_name TEXT NOT NULL,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    last_crawl TIMESTAMP WITH TIME ZONE DEFAULT NULL, -- Use timestamptz for time zone awareness
    UNIQUE(author_name, source)
);

-- Create publications table
CREATE TABLE publications (
    publication_id SERIAL PRIMARY KEY,
    author_id INTEGER NOT NULL REFERENCES authors(author_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    year INTEGER CHECK (year >= 0),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    source TEXT NOT NULL,
    UNIQUE(author_id, title)  -- Add unique constraint to prevent duplicate publications
);

-- Create indexes for performance
CREATE INDEX idx_authors_name_source ON authors(author_name, source);
CREATE INDEX idx_publications_author_id ON publications(author_id);

-- Transfer ownership of tables to the new user
ALTER TABLE authors OWNER TO publication_user;
ALTER TABLE publications OWNER TO publication_user;

-- No need for separate GRANT statements after ownership transfer, as default privileges are set

-- Connect as the new user to verify permissions
\c publication_db publication_user