-- Reset max_chapter_crawled về 0 để crawl lại chapter images từ đầu
-- Dùng khi bạn đã xóa nhầm dữ liệu trong bảng chapter_image

-- Bước 1: Xóa toàn bộ dữ liệu chapter_image
DELETE FROM chapter_image;

-- Bước 2: Reset max_chapter_crawled về 0 để crawl lại từ đầu
UPDATE manga SET max_chapter_crawled = 0;
