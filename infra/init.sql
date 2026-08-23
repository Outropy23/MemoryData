-- MemoryData Swarm64 Schema Bootstrap
-- Executed automatically by Docker entrypoint
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- Swarm64 DA is optional; graceful skip if not installed
DO $$ BEGIN
    CREATE EXTENSION IF NOT EXISTS swarm64da;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'swarm64da not available, running standard PostgreSQL mode';
END $$;
