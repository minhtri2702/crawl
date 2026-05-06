-- Migration: Add crawl_error_log table
-- Tracks failed chapter/image crawls for retry in subsequent runs.

CREATE TABLE IF NOT EXISTS crawl_error_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manga_id UUID NOT NULL REFERENCES manga(id) ON DELETE CASCADE,
    chapter_id INTEGER REFERENCES chapter(id) ON DELETE CASCADE,
    chapter_number INTEGER NOT NULL,
    chapter_url TEXT NOT NULL,
    error_type VARCHAR(50) NOT NULL,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_attempt TIMESTAMP NOT NULL DEFAULT NOW(),
    resolved INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Unique constraint: one error log per chapter_url + error_type
    CONSTRAINT uq_chapter_url_error_type UNIQUE (chapter_url, error_type)
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_crawl_error_log_manga_id ON crawl_error_log(manga_id);
CREATE INDEX IF NOT EXISTS idx_crawl_error_log_chapter_id ON crawl_error_log(chapter_id);
CREATE INDEX IF NOT EXISTS idx_crawl_error_log_resolved ON crawl_error_log(resolved);
CREATE INDEX IF NOT EXISTS idx_crawl_error_log_retry_count ON crawl_error_log(retry_count);
