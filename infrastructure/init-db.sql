-- Initialize database with pgvector extension

-- Create vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create UUID extension for primary keys
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE dv360agent TO dvdbowner;

-- Log success
DO $$
BEGIN
    RAISE NOTICE 'Database initialized successfully';
END
$$;
