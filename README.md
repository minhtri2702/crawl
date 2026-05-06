# 🐍 Manga Crawler

A production-ready web crawler system built with Python, Selenium, and PostgreSQL that scrapes manga data from [truyenqqno.com](https://truyenqqno.com/).

## 📋 Features

- **Listing Page Crawling**: Extracts manga title, detail URL, cover image URL, and latest chapter number
- **Detail Page Crawling**: Extracts full metadata (description, author, status) and complete chapter list
- **Image Downloading**: Downloads cover images and stores them locally with slugified filenames
- **Database Storage**: PostgreSQL with SQLAlchemy ORM for manga and chapter data
- **Smart Upsert Logic**: Detects new vs existing manga; only inserts new chapters for existing entries
- **Scheduled Execution**: APScheduler for daily crawling at 2:00 AM
- **Retry Mechanism**: Exponential backoff retry for Selenium operations
- **Docker Support**: Full Docker Compose setup with PostgreSQL and crawler services
- **Logging**: Rotating file and console logging with configurable levels

## 🏗️ Project Structure

```
crawl/
├── crawler/
│   ├── __init__.py
│   ├── coordinator.py      # Orchestrates the full crawling pipeline
│   ├── detail_crawler.py   # Manga detail page scraper
│   ├── driver.py           # Selenium WebDriver factory with retry
│   └── listing_crawler.py  # Listing page scraper
├── db/
│   ├── __init__.py
│   ├── config.py           # Database configuration from env vars
│   └── session.py          # SQLAlchemy engine and session management
├── models/
│   ├── __init__.py
│   ├── chapter.py          # Chapter ORM model
│   └── manga.py            # Manga ORM model
├── services/
│   ├── __init__.py
│   ├── image_service.py    # Image download and storage service
│   └── manga_service.py    # Database CRUD operations
├── utils/
│   ├── __init__.py
│   ├── helpers.py          # Slugify, retry decorator, URL utilities
│   └── logging_setup.py    # Logging configuration
├── data/
│   └── images/             # Downloaded cover images
├── logs/                   # Application logs
├── .env                    # Environment variables (not committed)
├── .env.example            # Environment variables template
├── .gitignore
├── docker-compose.yml      # Docker Compose configuration
├── Dockerfile              # Docker image definition
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
└── README.md
```

## 🗄️ Database Schema

### manga table
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER (PK) | Auto-increment ID |
| title | VARCHAR(500) | Manga title |
| url | VARCHAR(1000) (UNIQUE) | Manga detail page URL |
| cover_image_path | VARCHAR(1000) | Local path to cover image |
| status | VARCHAR(50) | Ongoing / Completed |
| description | TEXT | Manga description |
| author | VARCHAR(255) | Author name |
| created_at | DATETIME | Record creation timestamp |
| updated_at | DATETIME | Record update timestamp |

### chapter table
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER (PK) | Auto-increment ID |
| manga_id | INTEGER (FK) | Reference to manga.id |
| chapter_number | FLOAT | Chapter number |
| chapter_name | VARCHAR(500) | Chapter name/title |
| url | VARCHAR(1000) (UNIQUE) | Chapter URL |
| created_at | DATETIME | Record creation timestamp |

## 🚀 How to Run

### Option 1: Docker Compose (Recommended)

```bash
# 1. Clone the repository
git clone <repo-url>
cd crawl

# 2. Copy environment file
cp .env.example .env

# 3. Build and start all services
docker-compose up -d --build

# 4. View logs
docker-compose logs -f crawler

# 5. Stop services
docker-compose down
```

The crawler will run daily at 2:00 AM in scheduled mode.

### Option 2: Local Development

#### Prerequisites
- Python 3.11+
- PostgreSQL 15 (running on localhost:5433)
- Google Chrome browser
- ChromeDriver (managed automatically by webdriver-manager)

#### Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd crawl

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env if needed (defaults match Docker PostgreSQL)

# 5. Start PostgreSQL (if not running)
# Using Docker for PostgreSQL only:
docker run -d \
  --name crawler-postgres \
  -e POSTGRES_DB=crawler_db \
  -e POSTGRES_USER=crawler_admin \
  -e POSTGRES_PASSWORD=0000 \
  -p 5433:5432 \
  postgres:15

# 6. Run the crawler (one-time mode)
python main.py --mode once

# 7. Run with custom options
python main.py --mode once --pages 3 --start-page 1 --no-headless

# 8. Run in scheduled mode (daily at 2 AM)
python main.py --mode scheduled
```

## ⚙️ Configuration

All configuration is managed via environment variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| DB_HOST | localhost | PostgreSQL host |
| DB_PORT | 5433 | PostgreSQL port |
| DB_NAME | crawler_db | Database name |
| DB_USER | crawler_admin | Database user |
| DB_PASSWORD | 0000 | Database password |
| CRAWLER_BASE_URL | https://truyenqqno.com | Target website |
| CRAWLER_START_PAGE | 1 | Starting page number |
| CRAWLER_MAX_PAGES | 5 | Number of pages to crawl |
| CRAWLER_HEADLESS | true | Run browser in headless mode |
| CRAWLER_PAGE_LOAD_TIMEOUT | 30 | Page load timeout in seconds |
| CRAWLER_RETRY_MAX_ATTEMPTS | 3 | Max retry attempts |
| CRAWLER_RETRY_DELAY | 5 | Initial retry delay in seconds |
| IMAGE_SAVE_PATH | ./data/images | Image storage directory |
| LOG_LEVEL | INFO | Logging level |
| LOG_FILE | ./logs/crawler.log | Log file path |

## 🧠 Architecture

### Crawling Flow

1. **Listing Crawler** scrapes the "truyen-moi-cap-nhat" pages to get manga URLs
2. **Detail Crawler** visits each manga detail page to extract full metadata and chapters
3. **Image Service** downloads cover images to local storage
4. **Manga Service** stores/updates data in PostgreSQL using upsert logic:
   - If manga URL exists → update metadata, insert only new chapters
   - If manga URL is new → insert manga + all chapters

### Retry Mechanism

The `@retry` decorator provides exponential backoff for Selenium operations:
- 3 attempts by default
- Initial 5-second delay, doubling each retry
- Catches and retries on specified exceptions

## 📊 Output

- **Database**: Manga and chapter data stored in PostgreSQL
- **Images**: Cover images saved to `./data/images/` with slugified filenames
- **Logs**: Detailed logs in `./logs/crawler.log` and console

## 🐳 Docker Services

### PostgreSQL Service
- Image: `postgres:15`
- Container: `crawler-postgres`
- Port: `5433:5432`
- Volume: `crawler-postgres-data` (persistent storage)
- Health check: `pg_isready`

### Crawler Service
- Build: From Dockerfile
- Container: `manga-crawler`
- Depends on: PostgreSQL (waits for healthy status)
- Runs: Scheduled mode (daily at 2:00 AM)
- Volumes: `crawler-data` (images), `crawler-logs` (logs)

## 📝 License

MIT
