-- Enable vector support when PostgreSQL initializes a fresh data volume.
-- This is not the application schema or a replacement for versioned database migrations.
CREATE EXTENSION IF NOT EXISTS vector;
