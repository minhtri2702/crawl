"""
Crawler coordinator.
Orchestrates the full crawling process: listing -> detail -> DB -> images.
"""

import os
import logging
from typing import Optional

from selenium.webdriver.remote.webdriver import WebDriver

from crawler.driver import WebDriverFactory
from crawler.listing_crawler import ListingCrawler
from crawler.detail_crawler import DetailCrawler
from services.manga_service import MangaService
from services.image_service import ImageService
from db.session import SessionLocal, init_db

logger = logging.getLogger(__name__)


class CrawlerCoordinator:
    """
    Coordinates the entire crawling workflow:
    1. Crawl listing pages to get manga URLs
    2. Check if manga already exists in DB (skip detail crawl if exists)
    3. Crawl each new manga detail page
    4. Download cover images to data/{slug}/{slug}.{ext}
    5. Store data in database
    """

    def __init__(
        self,
        base_url: str = "https://truyenqqno.com",
        start_page: int = 1,
        max_pages: int = 5,
        headless: bool = True,
        page_load_timeout: int = 30,
        data_path: str = "./data",
    ):
        self.base_url = base_url
        self.start_page = start_page
        self.max_pages = max_pages
        self.headless = headless
        self.page_load_timeout = page_load_timeout
        self.data_path = data_path

        self.driver_factory = WebDriverFactory(
            headless=headless,
            page_load_timeout=page_load_timeout,
        )
        self.driver: Optional[WebDriver] = None

    def run(self) -> dict:
        """
        Execute the full crawling pipeline.

        Returns:
            Dict with summary statistics.
        """
        stats = {
            "pages_crawled": 0,
            "manga_found": 0,
            "manga_new": 0,
            "manga_existing": 0,
            "manga_skipped": 0,
            "chapters_new": 0,
            "images_downloaded": 0,
            "errors": 0,
        }

        try:
            # Initialize database
            logger.info("Initializing database...")
            init_db()

            # Create WebDriver
            logger.info("Creating WebDriver...")
            self.driver = self.driver_factory.create_driver()

            # Initialize crawlers and services
            listing_crawler = ListingCrawler(self.driver, self.base_url)
            detail_crawler = DetailCrawler(self.driver, self.base_url)
            image_service = ImageService(self.data_path)

            # Get database session
            db_session = SessionLocal()
            manga_service = MangaService(db_session)

            try:
                # Step 1: Crawl listing pages
                all_listing_data = []
                for page in range(self.start_page, self.start_page + self.max_pages):
                    try:
                        page_data = listing_crawler.crawl_page(page)
                        if not page_data:
                            logger.info(
                                "No more data on page %d, stopping", page
                            )
                            break
                        all_listing_data.extend(page_data)
                        stats["pages_crawled"] += 1
                        stats["manga_found"] += len(page_data)
                        logger.info(
                            "Page %d: found %d manga entries",
                            page,
                            len(page_data),
                        )
                    except Exception as e:
                        logger.error(
                            "Error crawling page %d: %s", page, e
                        )
                        stats["errors"] += 1
                        continue

                logger.info(
                    "Total manga found from listing: %d",
                    len(all_listing_data),
                )

                # Step 2: Check each manga - skip if already exists in DB
                for idx, listing_item in enumerate(all_listing_data):
                    manga_url = listing_item["url"]
                    manga_title = listing_item["title"]

                    try:
                        # Check if manga already exists in database
                        existing_manga = manga_service.get_manga_by_url(manga_url)
                        if existing_manga:
                            logger.info(
                                "[%d/%d] Skipping (already in DB): %s (STT: %d)",
                                idx + 1,
                                len(all_listing_data),
                                manga_title,
                                existing_manga.stt,
                            )
                            stats["manga_skipped"] += 1
                            continue

                        logger.info(
                            "[%d/%d] Crawling detail: %s",
                            idx + 1,
                            len(all_listing_data),
                            manga_title,
                        )

                        # Step 3: Crawl detail page
                        detail_data = detail_crawler.crawl_detail(manga_url)
                        if not detail_data:
                            logger.warning(
                                "Failed to get detail for: %s", manga_title
                            )
                            stats["errors"] += 1
                            continue

                        # Step 4: Download cover image
                        cover_image_path = None
                        if detail_data.get("cover_image_url"):
                            cover_image_path = image_service.download_cover_image(
                                detail_data["cover_image_url"],
                                detail_data["title"],
                            )
                            if cover_image_path:
                                stats["images_downloaded"] += 1

                        # Step 5: Store in database
                        manga_data = {
                            "title": detail_data["title"],
                            "url": manga_url,
                            "cover_image_path": cover_image_path,
                            "status": detail_data.get("status"),
                            "description": detail_data.get("description"),
                            "author": detail_data.get("author"),
                            "alternative_titles": detail_data.get("alternative_titles"),
                            "created_date": detail_data.get("created_date"),
                            "translation_team": detail_data.get("translation_team"),
                            "age_rating": detail_data.get("age_rating"),
                            "likes": detail_data.get("likes"),
                            "followers": detail_data.get("followers"),
                            "views": detail_data.get("views"),
                            "genres": detail_data.get("genres"),
                        }

                        chapters_data = detail_data.get("chapters", [])

                        manga, is_new, new_chapters_count = (
                            manga_service.upsert_manga_with_chapters(
                                manga_data, chapters_data
                            )
                        )

                        if is_new:
                            stats["manga_new"] += 1
                        else:
                            stats["manga_existing"] += 1

                        stats["chapters_new"] += new_chapters_count

                        logger.info(
                            "Processed '%s' (STT: %d): %s, %d new chapters",
                            manga.title,
                            manga.stt,
                            "NEW" if is_new else "EXISTING",
                            new_chapters_count,
                        )

                    except Exception as e:
                        logger.error(
                            "Error processing manga '%s': %s",
                            manga_title,
                            e,
                        )
                        stats["errors"] += 1
                        # Rollback the session to clear the broken transaction
                        try:
                            db_session.rollback()
                        except Exception:
                            pass
                        continue

            finally:
                db_session.close()

        except Exception as e:
            logger.error("Crawler failed: %s", e)
            stats["errors"] += 1

        finally:
            # Clean up WebDriver
            if self.driver:
                self.driver_factory.destroy_driver(self.driver)

        # Log summary
        logger.info("=" * 50)
        logger.info("CRAWLING COMPLETE - SUMMARY")
        logger.info("=" * 50)
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")
        logger.info("=" * 50)

        return stats
