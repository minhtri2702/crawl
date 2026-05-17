# 📚 Manga Crawler - Tài Liệu Mã Nguồn

## Tổng Quan

Hệ thống crawler tự động thu thập dữ liệu manga từ [truyenqqko.com](https://truyenqqko.com), bao gồm thông tin metadata, danh sách chapter, và hình ảnh. Dữ liệu được lưu trữ trong PostgreSQL và hình ảnh được tải xuống local hoặc upload lên MinIO.

---

## 🏗️ Cấu Trúc Dự Án

```
crawl/
├── crawler/                  # Các module crawler
│   ├── __init__.py
│   ├── coordinator.py        # Điều phối toàn bộ quy trình crawl
│   ├── listing_crawler.py    # Crawl trang danh sách manga
│   ├── detail_crawler.py     # Crawl trang chi tiết manga
│   ├── chapter_image_crawler.py  # Crawl hình ảnh chapter
│   └── driver.py             # Quản lý Selenium WebDriver
├── db/                       # Database
│   ├── __init__.py
│   ├── config.py             # Cấu hình database từ biến môi trường
│   └── session.py            # SQLAlchemy engine & session management
├── models/                   # SQLAlchemy ORM models
│   ├── __init__.py
│   ├── manga.py              # Model Manga
│   ├── chapter.py            # Model Chapter & ChapterImage
│   ├── genre.py              # Model Genre & bảng trung gian manga_genre
│   └── crawl_error_log.py    # Model log lỗi crawl
├── services/                 # Business logic layer
│   ├── __init__.py
│   ├── manga_service.py      # CRUD operations cho manga & chapters
│   ├── image_service.py      # Download & upload ảnh bìa
│   └── minio_service.py      # Kết nối MinIO object storage
├── utils/                    # Tiện ích
│   ├── __init__.py
│   ├── helpers.py            # Slugify, retry decorator, URL utils
│   └── logging_setup.py      # Cấu hình logging
├── data/                     # Thư mục chứa dữ liệu tải về
├── logs/                     # Log files
├── main.py                   # Entry point chính
├── Dockerfile                # Docker image definition
├── docker-compose.yml        # Docker Compose configuration
├── requirements.txt          # Python dependencies
├── init_db.sql               # SQL khởi tạo database
├── run_migration.py          # Chạy migration
├── migration_add_stt_sequence.sql
├── migration_add_crawl_error_log.sql
├── migration_add_max_chapter_crawled.sql
├── migration_remove_stt.sql
├── test_db.py                # Script test kết nối database
├── DOCUMENTATION.md          # Tài liệu mã nguồn (file này)
└── .env.example              # Template biến môi trường
```

---

## 📦 Modules Chi Tiết

---

### 1. `main.py` - Entry Point

**Mô tả:** File chính để chạy ứng dụng. Hỗ trợ nhiều chế độ chạy khác nhau.

**Các hàm chính:**

| Hàm | Mô tả |
|------|-------------|
| `main()` | Entry point với argument parsing (argparse) |
| `run_crawler(max_pages, start_page, reverse)` | Chạy crawl metadata manga |
| `run_chapter_image_crawl(manga_id, max_chapters, headless)` | Chạy crawl hình ảnh chapter |
| `run_full_crawl(max_pages, max_chapters, headless)` | Chạy crawl toàn bộ (metadata + images) |
| `run_once(reverse)` | Chạy crawl một lần rồi thoát |
| `run_scheduled()` | Chạy theo lịch với APScheduler (mặc định 2:00 AM hàng ngày) |

**Các chế độ CLI:**
```bash
python main.py --mode once          # Crawl metadata một lần
python main.py --mode scheduled     # Crawl theo lịch (daily 2AM)
python main.py --mode chapters      # Crawl hình ảnh chapter
python main.py --mode full          # Crawl toàn bộ
```

**Các tham số CLI:**
- `--pages N`: Số trang listing cần crawl
- `--start-page N`: Trang bắt đầu
- `--reverse`: Crawl từ trang cao xuống thấp
- `--chapters N`: Số chapter mới nhất cần crawl mỗi manga
- `--no-headless`: Chạy browser ở chế độ có giao diện
- `--manga-id UUID`: Chỉ crawl chapter cho manga có UUID cụ thể

---

### 2. `crawler/coordinator.py` - CrawlerCoordinator

**Mô tả:** Điều phối toàn bộ quy trình crawl metadata.

**Class:** `CrawlerCoordinator`

**Quy trình crawl:**
1. Khởi tạo database và WebDriver
2. Crawl các trang listing để lấy danh sách manga URLs
3. Kiểm tra manga đã tồn tại trong DB chưa (bỏ qua nếu có)
4. Crawl trang chi tiết từng manga mới
5. Download ảnh bìa
6. Lưu dữ liệu vào database

**Phương thức chính:**
- `__init__(base_url, start_page, max_pages, headless, page_load_timeout, data_path, reverse)`: Khởi tạo coordinator
- `run()`: Thực thi pipeline crawl, trả về dict thống kê

**Các chỉ số thống kê trả về:**
```python
{
    "pages_crawled": 0,      # Số trang đã crawl
    "manga_found": 0,        # Số manga tìm thấy
    "manga_new": 0,          # Số manga mới
    "manga_existing": 0,     # Số manga đã tồn tại
    "manga_skipped": 0,      # Số manga bỏ qua
    "chapters_new": 0,       # Số chapter mới
    "images_downloaded": 0,  # Số ảnh đã tải
    "errors": 0,             # Số lỗi
}
```

---

### 3. `crawler/listing_crawler.py` - ListingCrawler

**Mô tả:** Crawl trang danh sách manga (`/truyen-moi-cap-nhat/trang-{page}`).

**Class:** `ListingCrawler`

**Phương thức chính:**
- `crawl_page(page_number)`: Crawl một trang listing, trả về list[dict] với keys: `title`, `url`, `cover_image_url`, `latest_chapter`
- `get_total_pages()`: Lấy tổng số trang listing

**Chi tiết xử lý:**
- Sử dụng `@retry` decorator (3 lần, exponential backoff)
- Thử nhiều CSS selectors khác nhau để tìm manga items
- Fallback selector: `a[href*='/truyen-']`
- Trích xuất title, URL, ảnh bìa, chapter mới nhất từ mỗi item

---

### 4. `crawler/detail_crawler.py` - DetailCrawler

**Mô tả:** Crawl trang chi tiết manga để lấy metadata đầy đủ và danh sách chapter.

**Class:** `DetailCrawler`

**Phương thức chính:**
- `crawl_detail(url)`: Crawl trang chi tiết, trả về dict với các keys:

```python
{
    "title": str,                    # Tên manga
    "description": str,              # Mô tả
    "author": str,                   # Tác giả
    "status": str,                   # Trạng thái (ongoing/completed)
    "cover_image_url": str,          # URL ảnh bìa
    "alternative_titles": str,       # Tên khác
    "created_date": str,             # Ngày tạo
    "translation_team": str,         # Nhóm dịch
    "age_rating": str,               # Độ tuổi
    "likes": int,                    # Lượt thích
    "followers": int,                # Lượt theo dõi
    "views": int,                    # Lượt xem
    "genres": list[str],             # Danh sách thể loại
    "chapters": list[dict],          # Danh sách chapter
}
```

**Các phương thức trích xuất:**
- `_extract_title()`: Tìm title qua nhiều selectors
- `_extract_description()`: Lấy mô tả
- `_extract_author()`: Lấy tác giả (có fallback regex)
- `_extract_status()`: Lấy trạng thái (có fallback regex)
- `_extract_cover_image()`: Lấy URL ảnh bìa
- `_extract_alternative_titles()`: Tên khác
- `_extract_created_date()`: Ngày tạo
- `_extract_translation_team()`: Nhóm dịch
- `_extract_age_rating()`: Độ tuổi
- `_extract_likes()`, `_extract_followers()`, `_extract_views()`: Số liệu thống kê
- `_extract_genres()`: Thể loại
- `_extract_chapters()`: Danh sách chapter (đã sort theo số)

---

### 5. `crawler/chapter_image_crawler.py` - ChapterImageCrawler

**Mô tả:** Crawl hình ảnh từ các trang chapter. Module phức tạp nhất trong hệ thống.

**Class:** `ChapterImageCrawler`

**Chiến lược crawl:**
1. Lấy `max_chapter` từ bảng `chapter` (chapter cao nhất trong DB)
2. Lấy `max_chapter_crawled` từ bảng `manga` (chapter đã crawl ảnh cao nhất)
3. Xác định range chapter cần crawl:
   - Nếu `max_chapters_per_manga` được set: crawl N chapter mới nhất
   - Nếu `max_chapters_per_manga` là None: crawl từ `max_chapter` xuống `max_chapter_crawled + 1`
4. Lưu thông tin ảnh vào bảng `chapter_image`
5. Update `manga.max_chapter_crawled`

**Phương thức chính:**
- `crawl_all_manga_chapters(manga_ids, max_chapters_per_manga)`: Crawl chapter images cho tất cả manga
- `_crawl_chapter_by_number(manga, manga_slug, chapter_number, chapter_url, db)`: Crawl một chapter cụ thể
- `_retry_failed_chapters(manga, manga_slug, db, max_retries)`: Thử lại các chapter bị lỗi
- `_extract_image_urls()`: Trích xuất URLs ảnh từ trang chapter (3 strategies)
- `_download_image(image_url, filepath, page_num, manga_slug, chapter_number)`: Download ảnh và upload lên MinIO

**Xử lý lỗi:**
- Phát hiện redirect (404, redirect về detail page, listing page)
- Log lỗi vào bảng `crawl_error_log` với cơ chế retry
- Tự động đánh dấu resolved khi crawl thành công

**Parallel downloading:**
- Sử dụng `ThreadPoolExecutor` với 5 workers để download ảnh song song

---

### 6. `crawler/driver.py` - WebDriverFactory

**Mô tả:** Factory tạo và quản lý Selenium WebDriver instances.

**Class:** `WebDriverFactory`

**Phương thức chính:**
- `__init__(headless, page_load_timeout, implicit_wait, page_load_strategy)`: Khởi tạo factory
- `create_driver()`: Tạo Chrome WebDriver với cấu hình:
  - Headless mode (mặc định)
  - Anti-detection options (ẩn automation)
  - Custom User-Agent
  - Eager page load strategy
  - CDP commands để mask automation
- `destroy_driver(driver)`: Đóng WebDriver an toàn

**Các tính năng chống phát hiện:**
- Ẩn `navigator.webdriver`
- Giả mạo `navigator.plugins`
- Thiết lập ngôn ngữ `vi-VN, vi, en-US, en`

---

### 7. `db/config.py` - DatabaseConfig

**Mô tả:** Cấu hình database từ biến môi trường.

**Class:** `DatabaseConfig`

**Properties:**
- `host`: DB_HOST (default: `100.94.58.103`)
- `port`: DB_PORT (default: `5433`)
- `database`: DB_NAME (default: `crawler_db`)
- `username`: DB_USER (default: `crawler_admin`)
- `password`: DB_PASSWORD (default: `0000`)
- `database_url`: PostgreSQL connection URL

---

### 8. `db/session.py` - Session Management

**Mô tả:** Quản lý SQLAlchemy engine và session.

**Các thành phần:**
- `engine`: SQLAlchemy engine với connection pooling (pool_size=10, max_overflow=20)
- `SessionLocal`: Session factory (autocommit=False, autoflush=False)
- `Base`: Declarative base cho ORM models
- `init_db()`: Tạo tất cả bảng từ models
- `drop_db()`: Xóa tất cả bảng

**PostgreSQL connection options:**
- `connect_timeout`: 10s
- `keepalives`: enabled
- `statement_timeout`: 30s
- `lock_timeout`: 10s

---

### 9. Models (SQLAlchemy ORM)

#### `models/manga.py` - Manga

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | UUID tự sinh |
| `title` | VARCHAR(500) | Tên manga |
| `url` | VARCHAR(1000) (UNIQUE) | URL trang chi tiết |
| `cover_image_path` | VARCHAR(1000) | Đường dẫn ảnh bìa |
| `status` | VARCHAR(50) | Trạng thái (ongoing/completed) |
| `description` | TEXT | Mô tả |
| `author` | VARCHAR(255) | Tác giả |
| `alternative_titles` | TEXT | Tên khác |
| `created_date` | VARCHAR(50) | Ngày tạo |
| `translation_team` | VARCHAR(255) | Nhóm dịch |
| `age_rating` | VARCHAR(50) | Độ tuổi |
| `likes` | BIGINT | Lượt thích |
| `followers` | BIGINT | Lượt theo dõi |
| `views` | BIGINT | Lượt xem |
| `max_chapter_crawled` | Integer | Chapter cao nhất đã crawl ảnh |
| `created_at` | TIMESTAMPTZ | Thời gian tạo |
| `updated_at` | TIMESTAMPTZ | Thời gian cập nhật |

**Relationships:**
- `chapters`: One-to-many với Chapter (cascade delete)
- `genres`: Many-to-many với Genre qua bảng `manga_genre`

#### `models/chapter.py` - Chapter & ChapterImage

**Chapter:**
| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer (PK) | Auto-increment |
| `manga_id` | UUID (FK) | Reference đến manga |
| `chapter_number` | Float | Số chapter |
| `chapter_name` | VARCHAR(500) | Tên chapter |
| `url` | VARCHAR(1000) (UNIQUE) | URL chapter |
| `created_at` | TIMESTAMPTZ | Thời gian tạo |

**ChapterImage:**
| Column | Type | Description |
|--------|------|-------------|
| `chapter_id` | Integer (PK, FK) | Reference đến chapter (part of composite PK) |
| `page_order` | Integer (PK) | Thứ tự trang (part of composite PK) |
| `image_url` | VARCHAR(2000) | URL ảnh gốc |
| `image_path` | VARCHAR(1000) | Đường dẫn trên MinIO |
| `created_at` | TIMESTAMPTZ | Thời gian tạo |

**Composite Primary Key:** `(chapter_id, page_order)` - mỗi chapter không thể có 2 ảnh cùng số thứ tự.

#### `models/genre.py` - Genre

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer (PK) | Auto-increment |
| `name` | VARCHAR(100) (UNIQUE) | Tên thể loại |
| `slug` | VARCHAR(100) (UNIQUE) | Slug |
| `created_at` | TIMESTAMPTZ | Thời gian tạo |

**Bảng trung gian `manga_genre`:**
- `manga_id` (UUID, FK → manga.id)
- `genre_id` (Integer, FK → genre.id)

#### `models/crawl_error_log.py` - CrawlErrorLog

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | UUID tự sinh |
| `manga_id` | UUID (FK) | Reference đến manga |
| `chapter_id` | Integer (FK) | Reference đến chapter (nullable) |
| `chapter_number` | Integer | Số chapter bị lỗi |
| `chapter_url` | Text | URL chapter |
| `error_type` | VARCHAR(50) | Loại lỗi (redirect, timeout, no_images, ...) |
| `error_message` | Text | Chi tiết lỗi |
| `retry_count` | Integer | Số lần đã thử lại |
| `last_attempt` | DateTime | Lần thử cuối |
| `resolved` | Integer | 0=chưa giải quyết, 1=đã giải quyết |
| `created_at` | DateTime | Thời gian tạo |

**Unique constraint:** `(chapter_url, error_type)`

---

### 10. `services/manga_service.py` - MangaService

**Mô tả:** Service xử lý CRUD operations cho manga, chapters, genres.

**Class:** `MangaService`

**Phương thức chính:**
- `get_manga_by_url(url)`: Tìm manga theo URL
- `get_chapter_by_url(url)`: Tìm chapter theo URL
- `get_existing_chapter_urls(manga_id)`: Lấy set URLs chapter đã tồn tại
- `get_or_create_genre(name)`: Tìm hoặc tạo genre mới
- `set_manga_genres(manga, genre_names)`: Gán genres cho manga
- `create_manga(...)`: Tạo manga mới
- `update_manga(...)`: Cập nhật manga
- `create_chapter(...)`: Tạo chapter mới
- `bulk_create_chapters(manga_id, chapters_data)`: Bulk insert chapters (bỏ qua chapter đã tồn tại)
- `upsert_manga_with_chapters(manga_data, chapters_data)`: Upsert manga + chapters, trả về (Manga, is_new, new_chapters_count)

**Xử lý lỗi:** Khi bulk_create_chapters gặp lỗi, rollback session và tiếp tục với chapter tiếp theo.

---

### 11. `services/image_service.py` - ImageService

**Mô tả:** Service download và upload ảnh bìa lên MinIO.

**Class:** `ImageService`

**Phương thức chính:**
- `download_cover_image(image_url, title)`: Download ảnh bìa và upload trực tiếp lên MinIO (không lưu local)
- `get_manga_dir(title)`: Lấy đường dẫn thư mục manga
- `get_chapter_dir(title, chapter_number)`: Lấy đường dẫn thư mục chapter

**Lưu ý:** Ảnh bìa được upload trực tiếp lên MinIO từ memory, không lưu file tạm.

---

### 12. `services/minio_service.py` - MinioService

**Mô tả:** Service kết nối và thao tác với MinIO object storage.

**Class:** `MinioService`

**Phương thức chính:**
- `upload_file(local_file_path, object_name, bucket_name, content_type)`: Upload file local lên MinIO
- `upload_bytes(data, object_name, bucket_name, content_type)`: Upload bytes trực tiếp lên MinIO
- `get_public_url(object_name, bucket_name)`: Lấy public URL của object
- `object_exists(object_name, bucket_name)`: Kiểm tra object tồn tại
- `remove_object(object_name, bucket_name)`: Xóa object

---

### 13. `utils/helpers.py` - Utility Functions

**Các hàm:**

| Hàm | Mô tả |
|------|-------------|
| `remove_vietnamese_diacritics(text)` | Loại bỏ dấu tiếng Việt |
| `slugify(text)` | Chuyển text thành slug URL-friendly (vd: "Một Mình Ta" → "mot-minh-ta") |
| `retry(max_attempts, delay, backoff, exceptions)` | Decorator retry với exponential backoff |
| `extract_chapter_number(chapter_text)` | Trích xuất số chapter từ text (vd: "Chapter 1.5" → 1.5) |
| `normalize_url(url, base_url)` | Chuẩn hóa URL (thêm base URL nếu là relative) |

**Chi tiết `retry` decorator:**
- `max_attempts`: Số lần thử tối đa (mặc định: 3)
- `delay`: Thời gian delay ban đầu (mặc định: 5s)
- `backoff`: Hệ số nhân delay sau mỗi lần thử (mặc định: 2.0)
- `exceptions`: Tuple các exception cần bắt (mặc định: Exception)

---

### 14. `utils/logging_setup.py` - Logging Configuration

**Mô tả:** Cấu hình logging với RotatingFileHandler.

**Hàm:** `setup_logging(log_level, log_file, max_bytes, backup_count)`

**Cấu hình:**
- File handler: RotatingFileHandler (10MB mỗi file, giữ 5 backup)
- Console handler: StreamHandler
- Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- Tự động tắt verbose logging cho: selenium, urllib3, webdriver_manager

---

## 🖼️ Cách Ảnh Được Lưu Trữ

Hệ thống lưu trữ **2 loại ảnh** khác nhau, mỗi loại có cách lưu khác nhau:

### 1. Ảnh Bìa (Cover Image)

**Module xử lý:** `services/image_service.py` - `ImageService.download_cover_image()`

**Cách lưu:**
- **Chỉ lưu trên MinIO** (object storage), **KHÔNG lưu file local**
- Download ảnh từ URL gốc vào memory (`response.content`), sau đó upload thẳng lên MinIO
- Nếu MinIO chưa được cấu hình (`MINIO_ENDPOINT` không có trong `.env`), ảnh bìa sẽ **không được lưu** và `cover_image_path` trong DB sẽ là `NULL`

**Đường dẫn trên MinIO:**
```
{slug}/{slug}.{ext}
```
Ví dụ: `one-piece/one-piece.jpg`, `naruto/naruto.webp`

**Cơ chế:**
- Kiểm tra ảnh đã tồn tại trên MinIO chưa (`object_exists`) → nếu có thì bỏ qua
- Upload bằng `upload_bytes()` (từ memory, không qua file tạm)

### 2. Ảnh Chapter (Chapter Images)

**Module xử lý:** `crawler/chapter_image_crawler.py` - `ChapterImageCrawler._download_image()`

**Cách lưu:**
- **Chỉ lưu trên MinIO** (object storage), **KHÔNG lưu file local**
- Download ảnh từ URL gốc vào memory (`response.content`), sau đó upload thẳng lên MinIO
- Nếu MinIO chưa được cấu hình, ảnh chapter sẽ **không được lưu**

**Đường dẫn trên MinIO:**
```
{manga_slug}/chap-{chapter_number}/{page_number}{ext}
```
Ví dụ: `one-piece/chap-1/1.jpg`

**Cơ chế:**
- Kiểm tra ảnh đã tồn tại trong DB chưa → nếu có thì bỏ qua
- Kiểm tra ảnh đã tồn tại trên MinIO chưa (`object_exists`) → nếu có thì bỏ qua
- Download song song bằng `ThreadPoolExecutor` (5 workers)
- Upload bằng `upload_bytes()` (từ memory, không qua file tạm)
- Lưu metadata (image_url, image_path=MinIO path, page_order) vào bảng `chapter_image` trong DB

### 3. Lưu metadata trong Database

Bảng `chapter_image` lưu thông tin tham chiếu đến ảnh:

| Column | Ý nghĩa |
|--------|---------|
| `chapter_id` | FK → chapter.id |
| `image_url` | URL gốc của ảnh trên website nguồn |
| `image_path` | Đường dẫn trên MinIO (vd: `one-piece/chap-1/1.jpg`) |
| `page_order` | Thứ tự trang trong chapter (1, 2, 3...) |

### 4. Ảnh chapter và ảnh bìa có chung folder trên MinIO không?

**CÓ.** Hiện tại ảnh chapter và ảnh bìa được lưu **chung folder** theo tên truyện (slug):

| Loại ảnh | MinIO Path | Ví dụ |
|----------|-----------|-------|
| Ảnh bìa | `{slug}/{slug}.{ext}` | `one-piece/one-piece.jpg` |
| Ảnh chapter | `{slug}/chap-{n}/{page}.ext` | `one-piece/chap-1/1.jpg` |

Cấu trúc thư mục trên MinIO:
```
one-piece/
├── one-piece.jpg          # Ảnh bìa
├── chap-1/
│   ├── 1.jpg
│   ├── 2.jpg
│   └── ...
├── chap-2/
│   ├── 1.jpg
│   ├── 2.jpg
│   └── ...
└── ...
```

### Tóm tắt

| Loại ảnh | Local | MinIO | DB |
|----------|-------|-------|----|
| Ảnh bìa | ❌ Không lưu | ✅ `{slug}/{slug}.{ext}` | ✅ `manga.cover_image_path` |
| Ảnh chapter | ❌ Không lưu | ✅ `{slug}/chap-{n}/{page}.jpg` | ✅ `chapter_image` table |

---

## 🗄️ Database Schema (SQL)

Xem file `init_db.sql` cho full SQL schema. Các bảng chính:
- `manga` - Thông tin manga
- `chapter` - Danh sách chapter
- `genre` - Thể loại
- `manga_genre` - Liên kết manga-genre (many-to-many)
- `chapter_image` - Hình ảnh trong chapter
- `crawl_error_log` - Log lỗi crawl

---

## 🔄 Crawl Flow Chi Tiết

### Flow 1: Metadata Crawl (`--mode once`)

```
main.py
  └─ run_crawler()
       └─ CrawlerCoordinator.run()
            ├─ init_db()                    # Khởi tạo database tables
            ├─ WebDriverFactory.create_driver()  # Tạo Chrome WebDriver
            ├─ ListingCrawler.crawl_page()  # Crawl N trang listing
            │    └─ [page 1, page 2, ...]
            ├─ [for each manga]
            │    ├─ MangaService.get_manga_by_url()  # Kiểm tra tồn tại
            │    ├─ DetailCrawler.crawl_detail()     # Crawl trang chi tiết
            │    ├─ ImageService.download_cover_image()  # Download ảnh bìa
            │    └─ MangaService.upsert_manga_with_chapters()  # Lưu DB
            └─ WebDriverFactory.destroy_driver()  # Đóng WebDriver
```

### Flow 2: Chapter Image Crawl (`--mode chapters`)

```
main.py
  └─ run_chapter_image_crawl()
       ├─ WebDriverFactory.create_driver()
       ├─ ChapterImageCrawler.crawl_all_manga_chapters()
       │    ├─ [for each manga]
       │    │    ├─ _retry_failed_chapters()     # Thử lại chapter lỗi
       │    │    ├─ Xác định range chapter cần crawl
       │    │    ├─ [for each chapter]
       │    │    │    ├─ _crawl_chapter_by_number()
       │    │    │    │    ├─ driver.get(chapter_url)
       │    │    │    │    ├─ _wait_for_images()
       │    │    │    │    ├─ _extract_image_urls()
       │    │    │    │    └─ _download_image() (parallel)
       │    │    │    └─ Lưu ChapterImage records vào DB
       │    │    └─ Update manga.max_chapter_crawled
       │    └─ Log summary
       └─ WebDriverFactory.destroy_driver()
```

---

## ⚙️ Cấu Hình Biến Môi Trường

| Biến | Mặc định | Mô tả |
|------|---------|-------------|
| `DB_HOST` | `100.94.58.103` | PostgreSQL host |
| `DB_PORT` | `5433` | PostgreSQL port |
| `DB_NAME` | `crawler_db` | Database name |
| `DB_USER` | `crawler_admin` | Database user |
| `DB_PASSWORD` | `0000` | Database password |
| `CRAWLER_BASE_URL` | `https://truyenqqko.com` | Target website |
| `CRAWLER_START_PAGE` | `1` | Trang bắt đầu |
| `CRAWLER_MAX_PAGES` | `5` | Số trang listing cần crawl |
| `CRAWLER_HEADLESS` | `true` | Chạy browser headless |
| `CRAWLER_PAGE_LOAD_TIMEOUT` | `30` | Timeout load trang (giây) |
| `DATA_PATH` | `./data` | Thư mục chứa dữ liệu |
| `MINIO_ENDPOINT` | (optional) | MinIO server endpoint |
| `MINIO_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `MINIO_SECRET_KEY` | `minioadmin` | MinIO secret key |
| `MINIO_BUCKET` | `manga-images` | MinIO bucket name |
| `MINIO_SECURE` | `false` | Sử dụng HTTPS cho MinIO |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FILE` | `./logs/crawler.log` | Đường dẫn file log |

---

## 🐳 Docker Deployment

### Docker Compose Services:

1. **PostgreSQL** (`postgres:15`)
   - Port: `5433:5432`
   - Volume: `crawler-postgres-data`
   - Health check: `pg_isready`

2. **Crawler** (built from Dockerfile)
   - Depends on: PostgreSQL (healthy)
   - Command: `python main.py --mode scheduled`
   - Volumes: `crawler-data`, `crawler-logs`

### Dockerfile:
- Base image: `python:3.11-slim`
- Cài đặt Google Chrome + dependencies
- Cài đặt Python packages từ requirements.txt
- Mặc định chạy: `python main.py --mode once`

---

## 🛠️ Xử Lý Lỗi & Retry

### Retry Mechanism:
- **Selenium operations**: `@retry` decorator (3 attempts, exponential backoff)
- **Chapter image crawl**: Retry qua `_retry_failed_chapters()` (tối đa 3 lần)
- **WebDriver creation**: `@retry` decorator với `WebDriverException`

### Error Logging:
- Lỗi chapter được log vào bảng `crawl_error_log`
- Mỗi lỗi có `error_type` riêng: `redirect`, `timeout`, `no_images`, `download_failed`
- Unique constraint trên `(chapter_url, error_type)` để tránh duplicate
- Tự động đánh dấu `resolved=1` khi crawl thành công

### Transaction Management:
- Rollback session khi gặp lỗi để tránh broken transaction
- Re-add objects vào session sau rollback

---

## ⚠️ Các Trường Hợp Lỗi & Xử Lý

### 1. `cover_image_path` bị NULL

Cột `cover_image_path` trong bảng `manga` có `nullable=True`, do đó có thể bị `NULL` trong nhiều trường hợp:

| Tình huống | `cover_image_path` | Giải thích |
|------------|-------------------|-------------|
| Manga mới, không có `cover_image_url` từ detail page | `NULL` | Không tìm thấy ảnh bìa trên trang |
| Manga mới, có `cover_image_url` nhưng MinIO chưa được cấu hình | `NULL` | `image_service.py` dòng 46-48: trả về `None` ngay nếu `self.minio` là `None` |
| Manga mới, có `cover_image_url`, MinIO có cấu hình nhưng upload thất bại | `NULL` | `image_service.py` dòng 97-103: exception khi upload |
| Manga mới, có `cover_image_url`, download ảnh thất bại (network error) | `NULL` | `image_service.py` dòng 89-96: `requests.RequestException` |
| Manga cũ, đã có `cover_image_path`, lần crawl sau không có ảnh mới | **Giữ nguyên giá trị cũ** | `manga_service.py` dòng 139: `if cover_image_path is not None` → không update |
| Manga cũ, chưa có `cover_image_path`, lần crawl sau có ảnh | **Được cập nhật** | `manga_service.py` dòng 139: `if cover_image_path is not None` → update thành công |

**Cơ chế bảo vệ:** Trong `update_manga()`, tham số `cover_image_path` chỉ được cập nhật nếu khác `None`. Điều này ngăn không cho ghi đè giá trị cũ bằng `None` khi crawl lại.

### 2. Các lỗi thường gặp khác

| Loại lỗi | Module | Xử lý |
|----------|--------|-------|
| Timeout load trang | `detail_crawler.py`, `chapter_image_crawler.py` | Retry với exponential backoff, log vào `crawl_error_log` |
| Redirect (404, redirect về listing) | `chapter_image_crawler.py` | Phát hiện qua URL hiện tại và page title, log error |
| Không tìm thấy chapter images | `chapter_image_crawler.py` | Log error type `no_images`, retry sau |
| StaleElementReferenceException | `listing_crawler.py`, `detail_crawler.py` | Bỏ qua item lỗi, tiếp tục với item tiếp theo |
| WebDriver creation failure | `driver.py` | Retry 3 lần với `@retry` decorator |
| Database connection failure | `db/session.py` | Connection pooling với `pool_pre_ping=True`, timeout 10s |
| Broken transaction | `coordinator.py`, `chapter_image_crawler.py` | Rollback session, tiếp tục với item tiếp theo |

---

## 📝 Ghi Chú Phát Triển

### Anti-Detection:
- Ẩn `navigator.webdriver`
- Giả mạo plugins và languages
- Custom User-Agent
- Eager page load strategy (không đợi tài nguyên không cần thiết)

### Performance:
- Connection pooling (pool_size=10, max_overflow=20)
- Parallel image downloading (ThreadPoolExecutor, 5 workers)
- Eager page load strategy
- Batch insert chapters

### Database:
- UUID primary keys cho manga và error logs
- Indexes trên các cột thường query
