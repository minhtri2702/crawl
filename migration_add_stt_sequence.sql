-- Migration: Add STT sequence for manga table
-- This replaces the FOR UPDATE locking approach with a PostgreSQL sequence,
-- allowing multiple crawler instances to safely insert manga concurrently.

-- Create sequence for manga STT
CREATE SEQUENCE IF NOT EXISTS manga_stt_seq START 1;

-- Update existing manga records to use sequence values
-- (This ensures existing records keep their current STT)
SELECT setval('manga_stt_seq', COALESCE((SELECT MAX(stt) FROM manga), 0));

-- Note: The manga.stt column already has a SERIAL type, but the application
-- code will now use nextval('manga_stt_seq') instead of SELECT ... FOR UPDATE.
-- The SERIAL default will only be used as fallback if the application doesn't
-- provide an STT value.
