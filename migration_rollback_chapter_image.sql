-- Rollback: Khôi phục bảng chapter_image với cấu trúc cũ (có cột id SERIAL PRIMARY KEY)
-- Dùng khi bạn đã xóa nhầm bảng chapter_image

CREATE TABLE IF NOT EXISTS chapter_image (
    id SERIAL PRIMARY KEY,
    chapter_id INTEGER NOT NULL REFERENCES chapter(id) ON DELETE CASCADE,
    image_url VARCHAR(2000) NOT NULL,
    image_path VARCHAR(1000),
    page_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_chapter_image_chapter_id ON chapter_image(chapter_id);
