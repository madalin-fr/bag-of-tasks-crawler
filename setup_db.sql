-- Drop existing database and user if they exist
DROP DATABASE IF EXISTS publication_db;
DROP USER IF EXISTS publication_user;

-- Create the database and user
CREATE DATABASE publication_db;
CREATE USER publication_user WITH PASSWORD 'project';

-- Connect to the database as postgres user to set up permissions
\c publication_db postgres

-- Grant permissions to the user
GRANT CONNECT ON DATABASE publication_db TO publication_user;
GRANT USAGE ON SCHEMA public TO publication_user;
GRANT CREATE ON SCHEMA public TO publication_user;

-- Grant specific table privileges for better security and maintenance
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO publication_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO publication_user;

-- Create tables as the owner (postgres)
CREATE TABLE authors (
    author_id SERIAL PRIMARY KEY,
    author_name TEXT NOT NULL,
    source TEXT NOT NULL,
    last_crawl TIMESTAMP DEFAULT NULL,
    UNIQUE(author_name, source)  -- Added unique constraint
);

CREATE TABLE publications (
    publication_id SERIAL PRIMARY KEY,
    author_id INTEGER NOT NULL REFERENCES authors(author_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    year INTEGER CHECK (year >= 0), -- Ensure valid years
    source TEXT NOT NULL
);

-- Create indexes for performance
CREATE INDEX idx_authors_name_source ON authors(author_name, source);
CREATE INDEX idx_publications_author_id ON publications(author_id);

-- Transfer ownership of tables to the new user
ALTER TABLE authors OWNER TO publication_user;
ALTER TABLE publications OWNER TO publication_user;

-- Grant privileges on the tables to the user
GRANT SELECT, INSERT, UPDATE, DELETE ON authors TO publication_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON publications TO publication_user;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO publication_user;

-- Connect as the new user to verify permissions
\c publication_db publication_user