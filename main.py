"""
Main entry point for the manga crawler application.
Supports:
  - One-time manga metadata crawl
  - Scheduled daily crawl via APScheduler
  - Chapter image crawl (downloads images from chapter pages)
  - Full crawl (metadata + chapter images)
"""

import os
import sys
import logging
import argparse

from dotenv import load_dotenv

# Load environment variables before any other imports
load_dotenv()

from utils.logging_setup import setup_logging
from crawler.coordinator import CrawlerCoordinator
from crawler.chapter_image_crawler import ChapterImageCrawler
from crawler.driver import WebDriverFactory
from db.session import SessionLocal
from models.manga import Manga
from models.chapter import Chapter
from utils.helpers import slugify

logger = logging.getLogger(__name__)


def run_crawler(max_pages: int = None, start_page: int = None) -> dict:
    """
    Execute the manga metadata crawler with configuration from environment variables.

    Args:
        max_pages: Override max pages from .env
        start_page: Override start page from .env

    Returns:
        Dict with crawling statistics.
    """
    base_url = os.getenv("CRAWLER_BASE_URL", "https://truyenqqno.com")
    if start_page is None:
        start_page = int(os.getenv("CRAWLER_START_PAGE", "1"))
    if max_pages is None:
        max_pages = int(os.getenv("CRAWLER_MAX_PAGES", "5"))
    headless = os.getenv("CRAWLER_HEADLESS", "true").lower() == "true"
    page_load_timeout = int(os.getenv("CRAWLER_PAGE_LOAD_TIMEOUT", "30"))
    data_path = os.getenv("DATA_PATH", "./data")

    coordinator = CrawlerCoordinator(
        base_url=base_url,
        start_page=start_page,
        max_pages=max_pages,
        headless=headless,
        page_load_timeout=page_load_timeout,
        data_path=data_path,
    )

    stats = coordinator.run()
    return stats


def run_chapter_image_crawl(
    manga_stt: int = None,
    max_chapters: int = None,
    headless: bool = True,
) -> dict:
    """
    Execute the chapter image crawler.

    Args:
        manga_stt: If provided, only crawl chapters for this manga STT.
        max_chapters: Number of latest chapters to crawl per manga.
                      If None, crawl all chapters that haven't been crawled yet.
        headless: Whether to run browser in headless mode.

    Returns:
        Dict with crawling statistics.
    """
    base_url = os.getenv("CRAWLER_BASE_URL", "https://truyenqqno.com")
    page_load_timeout = int(os.getenv("CRAWLER_PAGE_LOAD_TIMEOUT", "30"))
    data_path = os.getenv("DATA_PATH", "./data")

    # Create WebDriver
    driver_factory = WebDriverFactory(
        headless=headless,
        page_load_timeout=page_load_timeout,
    )
    driver = driver_factory.create_driver()

    try:
        chapter_crawler = ChapterImageCrawler(
            driver=driver,
            base_url=base_url,
            data_path=data_path,
            page_load_timeout=page_load_timeout,
        )

        # If manga_stt is specified, find the manga ID
        manga_ids = None
        if manga_stt is not None:
            db = SessionLocal()
            try:
                manga = (
                    db.query(Manga)
                    .filter(Manga.stt == manga_stt)
                    .first()
                )
                if manga:
                    manga_ids = [manga.id]
                    logger.info(
                        "Filtering to manga STT %d: %s",
                        manga_stt,
                        manga.title,
                    )
                else:
                    logger.warning(
                        "Manga with STT %d not found in database",
                        manga_stt,
                    )
            finally:
                db.close()

        stats = chapter_crawler.crawl_all_manga_chapters(
            manga_ids=manga_ids,
            max_chapters_per_manga=max_chapters,
        )
        return stats

    finally:
        driver_factory.destroy_driver(driver)


def run_full_crawl(
    max_pages: int = None,
    max_chapters: int = None,
    headless: bool = True,
) -> dict:
    """
    Run a full crawl: metadata + chapter images.

    Args:
        max_pages: Number of listing pages to crawl.
        max_chapters: Number of latest chapters to crawl per manga.
        headless: Whether to run browser in headless mode.

    Returns:
        Dict with combined statistics.
    """
    logger.info("=" * 50)
    logger.info("FULL CRAWL: Phase 1 - Metadata")
    logger.info("=" * 50)

    meta_stats = run_crawler(max_pages=max_pages)

    logger.info("=" * 50)
    logger.info("FULL CRAWL: Phase 2 - Chapter Images")
    logger.info("=" * 50)

    chapter_stats = run_chapter_image_crawl(
        max_chapters=max_chapters,
        headless=headless,
    )

    combined = {
        "metadata": meta_stats,
        "chapter_images": chapter_stats,
    }

    logger.info("=" * 50)
    logger.info("FULL CRAWL COMPLETE")
    logger.info("  Metadata: %d new manga, %d errors",
                 meta_stats.get("manga_new", 0),
                 meta_stats.get("errors", 0))
    logger.info("  Chapter Images: %d chapters, %d images, %d errors",
                 chapter_stats.get("chapters_processed", 0),
                 chapter_stats.get("images_downloaded", 0),
                 chapter_stats.get("errors", 0))
    logger.info("=" * 50)

    return combined


def run_once() -> None:
    """Run the manga metadata crawler once and exit."""
    logger.info("Starting one-time crawl...")
    stats = run_crawler()

    if stats.get("errors", 0) > 0:
        logger.warning("Crawl completed with %d errors", stats["errors"])
        sys.exit(1)

    logger.info("Crawl completed successfully")
    sys.exit(0)


def run_scheduled() -> None:
    """
    Run the crawler on a schedule using APScheduler.
    Default: runs once per day at 2:00 AM.
    """
    from apscheduler.schedulers.blocking import BlockingScheduler

    scheduler = BlockingScheduler()

    # Schedule the crawler to run daily
    scheduler.add_job(
        run_crawler,
        "cron",
        hour=2,
        minute=0,
        id="daily_manga_crawl",
        name="Daily manga crawl",
        misfire_grace_time=3600,
        coalesce=True,
        max_instances=1,
    )

    logger.info(
        "Scheduler started. Crawler will run daily at 2:00 AM."
    )
    logger.info("Press Ctrl+C to stop.")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
        scheduler.shutdown()


def main() -> None:
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Manga Crawler - Scrapes manga data from truyenqqno.com"
    )
    parser.add_argument(
        "--mode",
        choices=["once", "scheduled", "chapters", "full"],
        default="once",
        help=(
            "Run mode: 'once' for one-time metadata crawl, "
            "'scheduled' for daily crawl, "
            "'chapters' to download chapter images, "
            "'full' to do metadata + chapter images"
        ),
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=None,
        help="Number of listing pages to crawl (overrides .env)",
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=None,
        help="Starting page number (overrides .env)",
    )
    parser.add_argument(
        "--chapters",
        type=int,
        default=None,
        help=(
            "Number of latest chapters to crawl per manga. "
            "If omitted, crawl all chapters that haven't been crawled yet."
        ),
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser in visible mode (not headless)",
    )
    parser.add_argument(
        "--manga-stt",
        type=int,
        default=None,
        help=(
            "For --mode chapters: only crawl chapters for this manga STT. "
            "If omitted, crawl all manga."
        ),
    )

    args = parser.parse_args()

    # Override env vars with CLI args if provided
    if args.pages is not None:
        os.environ["CRAWLER_MAX_PAGES"] = str(args.pages)
    if args.start_page is not None:
        os.environ["CRAWLER_START_PAGE"] = str(args.start_page)
    if args.no_headless:
        os.environ["CRAWLER_HEADLESS"] = "false"

    # Setup logging
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_file = os.getenv("LOG_FILE", "./logs/crawler.log")
    setup_logging(log_level=log_level, log_file=log_file)

    logger.info("=" * 50)
    logger.info("MANGA CRAWLER STARTING")
    logger.info("Mode: %s", args.mode)
    if args.pages:
        logger.info("Pages: %d", args.pages)
    if args.chapters:
        logger.info("Chapters per manga: %d", args.chapters)
    logger.info("=" * 50)

    headless = not args.no_headless

    if args.mode == "chapters":
        stats = run_chapter_image_crawl(
            manga_stt=args.manga_stt,
            max_chapters=args.chapters,
            headless=headless,
        )
        if stats.get("errors", 0) > 0:
            logger.warning(
                "Chapter crawl completed with %d errors",
                stats["errors"],
            )
            sys.exit(1)
        logger.info("Chapter crawl completed successfully")
        sys.exit(0)
    elif args.mode == "full":
        result = run_full_crawl(
            max_pages=args.pages,
            max_chapters=args.chapters,
            headless=headless,
        )
        meta_errors = result["metadata"].get("errors", 0)
        chapter_errors = result["chapter_images"].get("errors", 0)
        if meta_errors > 0 or chapter_errors > 0:
            logger.warning(
                "Full crawl completed with %d metadata errors, %d chapter errors",
                meta_errors,
                chapter_errors,
            )
            sys.exit(1)
        logger.info("Full crawl completed successfully")
        sys.exit(0)
    elif args.mode == "once":
        run_once()
    else:
        run_scheduled()


if __name__ == "__main__":
    main()
