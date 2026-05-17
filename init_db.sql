-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Sequence for manga STT (allows concurrent inserts from multiple crawlers)
CREATE SEQUENCE IF NOT EXISTS manga_stt_seq START 1;

-- Manga table
CREATE TABLE IF NOT EXISTS manga (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    stt INTEGER NOT NULL DEFAULT nextval('manga_stt_seq') UNIQUE,

    title VARCHAR(500) NOT NULL,
    url VARCHAR(1000) NOT NULL UNIQUE,
    cover_image_path VARCHAR(1000),
    status VARCHAR(50),
    description TEXT,
    author VARCHAR(255),
    alternative_titles TEXT,
    created_date VARCHAR(50),
    translation_team VARCHAR(255),
    age_rating VARCHAR(50),
    likes BIGINT DEFAULT 0,
    followers BIGINT DEFAULT 0,
    views BIGINT DEFAULT 0,
    max_chapter_crawled INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_manga_title ON manga(title);
CREATE INDEX IF NOT EXISTS ix_manga_url ON manga(url);
CREATE INDEX IF NOT EXISTS ix_manga_stt ON manga(stt);

-- Chapter table
CREATE TABLE IF NOT EXISTS chapter (
    id SERIAL PRIMARY KEY,
    manga_id UUID NOT NULL REFERENCES manga(id) ON DELETE CASCADE,
    chapter_number DOUBLE PRECISION NOT NULL,
    chapter_name VARCHAR(500),
    url VARCHAR(1000) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_chapter_manga_id ON chapter(manga_id);
CREATE INDEX IF NOT EXISTS ix_chapter_url ON chapter(url);

-- Genre table
CREATE TABLE IF NOT EXISTS genre (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    slug VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_genre_name ON genre(name);
CREATE INDEX IF NOT EXISTS ix_genre_slug ON genre(slug);

-- Manga-Genre association table
CREATE TABLE IF NOT EXISTS manga_genre (
    manga_id UUID NOT NULL REFERENCES manga(id) ON DELETE CASCADE,
    genre_id INTEGER NOT NULL REFERENCES genre(id) ON DELETE CASCADE,
    PRIMARY KEY (manga_id, genre_id)
);

CREATE INDEX IF NOT EXISTS ix_manga_genre_manga_id ON manga_genre(manga_id);
CREATE INDEX IF NOT EXISTS ix_manga_genre_genre_id ON manga_genre(genre_id);

-- Chapter image table
CREATE TABLE IF NOT EXISTS chapter_image (
    chapter_id INTEGER NOT NULL REFERENCES chapter(id) ON DELETE CASCADE,
    page_order INTEGER NOT NULL DEFAULT 0,
    image_url VARCHAR(2000) NOT NULL,
    image_path VARCHAR(1000),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (chapter_id, page_order)
);
