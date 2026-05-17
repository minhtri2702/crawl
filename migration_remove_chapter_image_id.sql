-- Migration: Remove chapter_image.id, use composite primary key (chapter_id, page_order)
-- 
-- Cách dùng:
--   1. Chạy script này để thay đổi cấu trúc bảng
--   2. Hoặc dùng: python run_migration.py migration_remove_chapter_image_id.sql

-- Bước 1: Xóa dữ liệu trùng lặp (nếu có cùng chapter_id + page_order)
DELETE FROM chapter_image a
USING chapter_image b
WHERE a.ctid < b.ctid
  AND a.chapter_id = b.chapter_id
  AND a.page_order = b.page_order;

-- Bước 2: Xóa index cũ (nếu có)
DROP INDEX IF EXISTS ix_chapter_image_chapter_id;

-- Bước 3: Tạo bảng mới với composite primary key
CREATE TABLE IF NOT EXISTS chapter_image_new (
    chapter_id INTEGER NOT NULL REFERENCES chapter(id) ON DELETE CASCADE,
    page_order INTEGER NOT NULL DEFAULT 0,
    image_url VARCHAR(2000) NOT NULL,
    image_path VARCHAR(1000),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (chapter_id, page_order)
);

-- Bước 4: Copy dữ liệu từ bảng cũ sang bảng mới
INSERT INTO chapter_image_new (chapter_id, page_order, image_url, image_path, created_at)
SELECT chapter_id, page_order, image_url, image_path, created_at
FROM chapter_image;

-- Bước 5: Xóa bảng cũ và đổi tên bảng mới
DROP TABLE chapter_image;
ALTER TABLE chapter_image_new RENAME TO chapter_image;
