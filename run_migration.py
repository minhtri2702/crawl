"""
Run database migrations.
Executes SQL migration files in order.
"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

from db.session import engine
from sqlalchemy import text

MIGRATIONS = [
    {
        "name": "add_max_chapter_crawled",
        "sql": "ALTER TABLE manga ADD COLUMN IF NOT EXISTS max_chapter_crawled INTEGER DEFAULT 0",
    },
    {
        "name": "add_crawl_error_log",
        "sql": """
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
                CONSTRAINT uq_chapter_url_error_type UNIQUE (chapter_url, error_type)
            )
        """,
    },
    {
        "name": "add_crawl_error_log_indexes",
        "sql": """
            CREATE INDEX IF NOT EXISTS idx_crawl_error_log_manga_id ON crawl_error_log(manga_id);
            CREATE INDEX IF NOT EXISTS idx_crawl_error_log_chapter_id ON crawl_error_log(chapter_id);
            CREATE INDEX IF NOT EXISTS idx_crawl_error_log_resolved ON crawl_error_log(resolved);
            CREATE INDEX IF NOT EXISTS idx_crawl_error_log_retry_count ON crawl_error_log(retry_count);
        """,
    },
]

with engine.connect() as conn:
    for migration in MIGRATIONS:
        try:
            conn.execute(text(migration["sql"]))
            conn.commit()
            print(f"✅ Migration successful: {migration['name']}")
        except Exception as e:
            conn.rollback()
            print(f"❌ Migration failed: {migration['name']}: {e}")

    print("\nAll migrations completed.")
