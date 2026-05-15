"""
Chapter image crawler.
Visits each chapter page, extracts all manga images, and downloads them
in order to: data/{manga_slug}/chap-{chapter_number}/

Strategy:
1. Get max chapter number from DB (from chapter table)
2. Get max_chapter_crawled from manga table (highest chapter already crawled for images)
3. Determine which chapters to crawl:
   - If max_chapters_per_manga is set: crawl that many latest chapters
     (from max_chapter down to max_chapter - N + 1)
   - If max_chapters_per_manga is None: crawl all chapters from max_chapter
     down to max_chapter_crawled + 1 (only new chapters)
4. Save image info to chapter_image table in DB
5. Update manga.max_chapter_crawled after successful crawl
"""

import os
import re
import time
import logging
import concurrent.futures
import threading
from typing import Optional

import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)

from datetime import datetime

from utils.helpers import slugify
from db.session import SessionLocal
from models.manga import Manga
from models.chapter import Chapter, ChapterImage
from models.crawl_error_log import CrawlErrorLog


# Thread-local storage for WebDriver instances
_thread_local = threading.local()


logger = logging.getLogger(__name__)


class ChapterImageCrawler:
    """
    Crawler for chapter images.
    Uses max chapter from DB and max_chapter_crawled from manga table
    to determine which chapters need crawling.
    Saves image metadata to DB.
    """

    def __init__(
        self,
        driver: WebDriver,
        base_url: str = "https://truyenqqno.com",
        data_path: str = "./data",
        page_load_timeout: int = 30,
    ):
        self.driver = driver
        self.base_url = base_url
        self.data_path = data_path
        self.page_load_timeout = page_load_timeout

    def crawl_all_manga_chapters(
        self,
        manga_ids: Optional[list] = None,
        max_chapters_per_manga: Optional[int] = None,
    ) -> dict:
        """
        Crawl chapter images for all manga (or specified manga IDs).

        For each manga:
          - Retry previously failed chapters (from crawl_error_log)
          - Get max chapter number from chapter table
          - Get max_chapter_crawled from manga table
          - Determine range:
            * If max_chapters_per_manga is set: crawl N latest chapters
              (from max_chapter down to max_chapter - N + 1)
            * If max_chapters_per_manga is None: crawl from max_chapter
              down to max_chapter_crawled + 1 (only new chapters)
          - Save image info to DB
          - Update manga.max_chapter_crawled

        Args:
            manga_ids: Optional list of manga UUIDs to process.
                       If None, process all manga.
            max_chapters_per_manga: Number of latest chapters to crawl per manga.
                                    If None, crawl all chapters that haven't
                                    been crawled yet.

        Returns:
            Dict with summary statistics.
        """
        stats = {
            "manga_processed": 0,
            "chapters_processed": 0,
            "images_downloaded": 0,
            "errors": 0,
            "retry_attempted": 0,
            "retry_succeeded": 0,
        }

        db = SessionLocal()
        try:
            # Get manga to process
            if manga_ids:
                mangas = (
                    db.query(Manga)
                    .filter(Manga.id.in_(manga_ids))
                    .order_by(Manga.stt)
                    .all()
                )
            else:
                mangas = db.query(Manga).order_by(Manga.stt.desc()).all()

            logger.info(
                "Starting chapter image crawl for %d manga", len(mangas)
            )

            for manga in mangas:
                # Rollback any leftover failed transaction before processing next manga
                try:
                    db.rollback()
                except Exception:
                    pass

                try:
                    manga_slug = slugify(manga.title)
                    logger.info(
                        "[STT %d] Processing chapters for: %s",
                        manga.stt,
                        manga.title,
                    )

                    # Step 1: Retry previously failed chapters for this manga
                    retry_stats = self._retry_failed_chapters(
                        manga=manga,
                        manga_slug=manga_slug,
                        db=db,
                    )
                    stats["retry_attempted"] += retry_stats["attempted"]
                    stats["retry_succeeded"] += retry_stats["succeeded"]
                    stats["images_downloaded"] += retry_stats["images_downloaded"]
                    stats["chapters_processed"] += retry_stats["chapters_processed"]

                    # Step 2: Get max chapter number from DB
                    max_chapter = (
                        db.query(Chapter)
                        .filter(Chapter.manga_id == manga.id)
                        .order_by(Chapter.chapter_number.desc())
                        .first()
                    )

                    if not max_chapter:
                        logger.info(
                            "  No chapters found for manga %s", manga.title
                        )
                        continue

                    max_chap_num = int(max_chapter.chapter_number)
                    already_crawled = manga.max_chapter_crawled or 0

                    logger.info(
                        "  Max chapter in DB: %d, Already crawled up to: %d",
                        max_chap_num,
                        already_crawled,
                    )

                    # Determine the range of chapters to crawl
                    if max_chapters_per_manga is not None:
                        # Crawl N latest chapters (from max down)
                        start_chap = max_chap_num
                        end_chap = max(1, max_chap_num - max_chapters_per_manga + 1)
                        logger.info(
                            "  Mode: crawl %d latest chapters (%d down to %d)",
                            max_chapters_per_manga,
                            start_chap,
                            end_chap,
                        )
                    else:
                        # Crawl only new chapters (from max down to already_crawled + 1)
                        if max_chap_num <= already_crawled:
                            logger.info(
                                "  All chapters already crawled (max=%d, crawled=%d). Skipping.",
                                max_chap_num,
                                already_crawled,
                            )
                            continue

                        start_chap = max_chap_num
                        end_chap = already_crawled + 1
                        logger.info(
                            "  Mode: crawl new chapters (%d down to %d, %d chapters)",
                            start_chap,
                            end_chap,
                            start_chap - end_chap + 1,
                        )

                    # Get chapter records from DB for the range we need to crawl
                    chapter_records = (
                        db.query(Chapter)
                        .filter(
                            Chapter.manga_id == manga.id,
                            Chapter.chapter_number.between(end_chap, start_chap),
                        )
                        .order_by(Chapter.chapter_number.desc())
                        .all()
                    )

                    if not chapter_records:
                        logger.info(
                            "  No chapter records found in DB for range %d-%d. Skipping.",
                            end_chap,
                            start_chap,
                        )
                        continue

                    logger.info(
                        "  Found %d chapter records in DB for range %d-%d",
                        len(chapter_records),
                        end_chap,
                        start_chap,
                    )

                    chapter_count = 0
                    for ch_record in chapter_records:
                        chap_num = int(ch_record.chapter_number)
                        try:
                            result = self._crawl_chapter_by_number(
                                manga=manga,
                                manga_slug=manga_slug,
                                chapter_number=chap_num,
                                chapter_url=ch_record.url,
                                db=db,
                            )
                            if result and result > 0:
                                stats["images_downloaded"] += result
                                # If this chapter had a previous error, mark it resolved
                                self._mark_error_resolved(
                                    db=db,
                                    chapter_url=ch_record.url,
                                )
                            chapter_count += 1
                            stats["chapters_processed"] += 1
                        except Exception as e:
                            logger.error(
                                "  Error processing chapter %d of '%s': %s",
                                chap_num,
                                manga.title,
                                e,
                            )
                            stats["errors"] += 1
                            # Rollback to clear the failed transaction
                            try:
                                db.rollback()
                            except Exception:
                                pass
                            continue

                    # Update max_chapter_crawled after processing all chapters
                    if chapter_count > 0:
                        manga.max_chapter_crawled = max_chap_num
                        db.commit()
                        logger.info(
                            "  Updated max_chapter_crawled to %d for '%s'",
                            max_chap_num,
                            manga.title,
                        )

                    stats["manga_processed"] += 1
                    logger.info(
                        "  Completed %d chapters for '%s' (from %d down to %d)",
                        chapter_count,
                        manga.title,
                        start_chap,
                        end_chap,
                    )

                except Exception as e:
                    logger.error(
                        "Error processing manga '%s': %s", manga.title, e
                    )
                    stats["errors"] += 1
                    # Rollback to clear the failed transaction
                    try:
                        db.rollback()
                    except Exception:
                        pass
                    continue

        finally:
            db.close()

        # Log summary
        logger.info("=" * 50)
        logger.info("CHAPTER IMAGE CRAWLING COMPLETE - SUMMARY")
        logger.info("=" * 50)
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")
        logger.info("=" * 50)

        return stats


    def _crawl_chapter_by_number(
        self,
        manga: Manga,
        manga_slug: str,
        chapter_number: int,
        chapter_url: str,
        db: SessionLocal,
    ) -> int:
        """
        Crawl a single chapter page by chapter number and download all images.
        Saves image metadata to chapter_image table.

        Args:
            manga: The Manga object.
            manga_slug: Slugified manga title.
            chapter_number: The chapter number (integer).
            chapter_url: The constructed URL for this chapter.
            db: Database session.

        Returns:
            Number of images downloaded.
        """
        chapter_dir = os.path.join(
            self.data_path,
            manga_slug,
            f"chap-{chapter_number}",
        )
        os.makedirs(chapter_dir, exist_ok=True)

        # Check if chapter already has images downloaded
        existing_images = self._count_existing_images(chapter_dir)
        if existing_images > 0:
            logger.info(
                "  Chapter %d already has %d images on disk, skipping",
                chapter_number,
                existing_images,
            )
            return 0

        logger.info(
            "  Crawling chapter %d: %s",
            chapter_number,
            chapter_url,
        )

        # Load the chapter page
        try:
            self.driver.get(chapter_url)
        except TimeoutException:
            logger.warning(
                "  Timeout loading chapter page: %s", chapter_url
            )
            self._log_error(
                db=db,
                manga_id=manga.id,
                chapter_id=None,
                chapter_number=chapter_number,
                chapter_url=chapter_url,
                error_type="timeout",
                error_message=f"Timeout loading page: {chapter_url}",
            )
            return 0

        # Check if page loaded successfully (not a 404 or redirect)
        current_url = self.driver.current_url
        page_title = self.driver.title

        # Detect redirect to listing page or manga detail page
        is_redirect = False
        redirect_reason = ""
        if "404" in current_url:
            is_redirect = True
            redirect_reason = "404"
        elif current_url == manga.url:
            is_redirect = True
            redirect_reason = "redirect_to_detail"
        elif "truyen-moi-cap-nhat" in current_url:
            is_redirect = True
            redirect_reason = "redirect_to_listing"
        elif "Danh Sách Truyện Tranh" in page_title:
            is_redirect = True
            redirect_reason = "listing_page_title"
        elif "-chap-" not in current_url:
            is_redirect = True
            redirect_reason = "no_chap_in_url"

        if is_redirect:
            logger.warning(
                "  Chapter %d page not found (redirect): %s -> %s (title: %s)",
                chapter_number,
                chapter_url,
                current_url,
                page_title,
            )
            self._log_error(
                db=db,
                manga_id=manga.id,
                chapter_id=None,
                chapter_number=chapter_number,
                chapter_url=chapter_url,
                error_type=f"redirect_{redirect_reason}",
                error_message=(
                    f"Redirected from {chapter_url} to {current_url} "
                    f"(title: {page_title})"
                ),
            )
            return 0

        # Wait for images to load

        self._wait_for_images()

        # Extract image URLs
        image_urls = self._extract_image_urls()
        if not image_urls:
            logger.warning(
                "  No images found for chapter %d: %s",
                chapter_number,
                chapter_url,
            )
            self._log_error(
                db=db,
                manga_id=manga.id,
                chapter_id=None,
                chapter_number=chapter_number,
                chapter_url=chapter_url,
                error_type="no_images",
                error_message="No valid chapter images found on page",
            )
            return 0


        logger.info(
            "  Found %d images for chapter %d",
            len(image_urls),
            chapter_number,
        )

        # Find the chapter record in DB
        chapter_record = (
            db.query(Chapter)
            .filter(
                Chapter.manga_id == manga.id,
                Chapter.chapter_number == float(chapter_number),
            )
            .first()
        )

        if not chapter_record:
            logger.warning(
                "  Chapter %d not found in DB for manga '%s'. Creating record.",
                chapter_number,
                manga.title,
            )
            chapter_record = Chapter(
                manga_id=manga.id,
                chapter_number=float(chapter_number),
                chapter_name=f"Chương {chapter_number}",
                url=chapter_url,
            )
            db.add(chapter_record)
            db.flush()  # Get the ID

        # Download images in parallel using ThreadPoolExecutor
        downloaded = 0
        download_tasks = []
        for idx, img_url in enumerate(image_urls):
            page_num = idx + 1
            ext = self._get_extension(img_url)
            filename = f"{page_num}{ext}"
            filepath = os.path.join(chapter_dir, filename)

            # Check if this image already exists in DB
            existing_image = (
                db.query(ChapterImage)
                .filter(
                    ChapterImage.chapter_id == chapter_record.id,
                    ChapterImage.page_order == page_num,
                )
                .first()
            )
            if existing_image:
                logger.debug(
                    "  Image %d already in DB, skipping", page_num
                )
                downloaded += 1
                continue

            if os.path.exists(filepath):
                logger.debug(
                    "  Image %d already exists on disk: %s",
                    page_num,
                    filepath,
                )
                downloaded += 1
                # Still save to DB if not there
                chapter_image = ChapterImage(
                    chapter_id=chapter_record.id,
                    image_url=img_url,
                    image_path=filepath,
                    page_order=page_num,
                )
                db.add(chapter_image)
                continue

            download_tasks.append((img_url, filepath, page_num))

        # Download remaining images in parallel
        if download_tasks:
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_to_info = {
                    executor.submit(self._download_image, url, path, num): (url, path, num)
                    for url, path, num in download_tasks
                }
                for future in concurrent.futures.as_completed(future_to_info):
                    img_url, filepath, page_num = future_to_info[future]
                    try:
                        if future.result():
                            downloaded += 1
                            chapter_image = ChapterImage(
                                chapter_id=chapter_record.id,
                                image_url=img_url,
                                image_path=filepath,
                                page_order=page_num,
                            )
                            db.add(chapter_image)
                    except Exception as e:
                        logger.error(
                            "  Failed to download image %d: %s",
                            page_num,
                            e,
                        )

        # Commit all image records for this chapter
        try:
            db.commit()
            logger.info(
                "  Saved %d image records to DB for chapter %d",
                downloaded,
                chapter_number,
            )
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            logger.error(
                "  Failed to save image records to DB for chapter %d: %s",
                chapter_number,
                e,
            )
            # Even if DB commit fails, images are saved on disk.
            # Return 0 so caller knows DB save failed and can retry later.
            downloaded = 0

        logger.info(
            "  Downloaded %d/%d images for chapter %d",
            downloaded,
            len(image_urls),
            chapter_number,
        )

        return downloaded

    def _wait_for_images(self) -> None:
        """Wait for images to load on the chapter page."""
        time.sleep(2)  # Initial wait for page to render

        # Try to wait for img.lazy elements
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "img.lazy"))
            )
        except TimeoutException:
            # Try alternative selectors
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "img[class*='lazy']")
                    )
                )
            except TimeoutException:
                logger.debug("No lazy images found, trying all images")

        # Scroll to load lazy images
        self._scroll_to_load_images()

    def _scroll_to_load_images(self) -> None:
        """Scroll the page to trigger lazy image loading."""
        try:
            # Get all lazy images
            images = self.driver.find_elements(
                By.CSS_SELECTOR, "img.lazy, img[data-original]"
            )
            if not images:
                return

            # Scroll to each image to trigger lazy loading
            for img in images:
                try:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});",
                        img,
                    )
                    time.sleep(0.3)
                except StaleElementReferenceException:
                    continue
                except Exception:
                    continue

            # Extra wait for images to fully load
            time.sleep(2)

        except Exception as e:
            logger.debug("Error during scroll: %s", e)

    def _extract_image_urls(self) -> list[str]:
        """
        Extract all image URLs from the chapter page.
        Uses <img class="lazy"> tags with data-original or src attributes.

        Returns:
            List of image URLs in page order.
        """
        image_urls = []

        # Strategy 1: Find img.lazy elements
        try:
            images = self.driver.find_elements(
                By.CSS_SELECTOR, "img.lazy"
            )
            for img in images:
                try:
                    # Try data-original first (lazy loading), then src
                    url = (
                        img.get_attribute("data-original")
                        or img.get_attribute("src")
                        or ""
                    )
                    if url and self._is_valid_image_url(url):
                        image_urls.append(url)
                except StaleElementReferenceException:
                    continue
        except NoSuchElementException:
            pass

        # Strategy 2: If no images found, try all img tags
        if not image_urls:
            try:
                images = self.driver.find_elements(By.CSS_SELECTOR, "img")
                for img in images:
                    try:
                        url = (
                            img.get_attribute("data-original")
                            or img.get_attribute("src")
                            or ""
                        )
                        if url and self._is_valid_image_url(url):
                            image_urls.append(url)
                    except StaleElementReferenceException:
                        continue
            except NoSuchElementException:
                pass

        # Strategy 3: Try reading from page source with regex
        if not image_urls:
            try:
                page_source = self.driver.page_source
                # Match img tags with lazy class and data-original/src
                patterns = [
                    r'<img[^>]*class="[^"]*lazy[^"]*"[^>]*data-original="([^"]+)"',
                    r'<img[^>]*data-original="([^"]+)"[^>]*class="[^"]*lazy[^"]*"',
                    r'<img[^>]*class="[^"]*lazy[^"]*"[^>]*src="([^"]+)"',
                ]
                for pattern in patterns:
                    matches = re.findall(pattern, page_source)
                    if matches:
                        image_urls = [
                            url
                            for url in matches
                            if self._is_valid_image_url(url)
                        ]
                        if image_urls:
                            break
            except Exception as e:
                logger.debug("Error extracting from page source: %s", e)

        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in image_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls

    def _is_valid_image_url(self, url: str) -> bool:
        """Check if a URL is a valid image URL."""
        if not url or url.startswith("data:"):
            return False
        # Filter out non-image URLs
        skip_patterns = [
            "avatar",
            "logo",
            "icon",
            "banner",
            "ads",
            "ad.",
        ]
        url_lower = url.lower()
        for pattern in skip_patterns:
            if pattern in url_lower:
                return False
        return True

    def _download_image(
        self, image_url: str, filepath: str, page_num: int
    ) -> bool:
        """
        Download a single image.

        Args:
            image_url: The image URL to download.
            filepath: The local file path to save to.
            page_num: The page number (for logging).

        Returns:
            True if download succeeded, False otherwise.
        """
        try:
            logger.debug(
                "  Downloading image %d: %s", page_num, image_url
            )

            response = requests.get(
                image_url,
                timeout=30,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Referer": self.base_url + "/",
                    "Accept": (
                        "image/webp,image/apng,image/*,*/*;q=0.8"
                    ),
                    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
                },
                stream=True,
            )
            response.raise_for_status()

            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.debug("  Saved: %s", filepath)
            return True

        except requests.RequestException as e:
            logger.error(
                "  Failed to download image %d (%s): %s",
                page_num,
                image_url,
                e,
            )
            return False
        except OSError as e:
            logger.error(
                "  Failed to save image %d: %s", page_num, e
            )
            return False

    def _log_error(
        self,
        db: SessionLocal,
        manga_id,
        chapter_id,
        chapter_number: int,
        chapter_url: str,
        error_type: str,
        error_message: str = None,
    ) -> None:
        """
        Log a crawl error to the crawl_error_log table.
        If the same error already exists (same chapter_url + error_type),
        increment retry_count instead of creating a new record.

        Args:
            db: Database session.
            manga_id: UUID of the manga.
            chapter_id: UUID of the chapter (or None).
            chapter_number: Chapter number.
            chapter_url: Chapter URL.
            error_type: Type of error (redirect, timeout, no_images, etc.).
            error_message: Optional error description.
        """
        try:
            # Check if this error already exists
            existing = (
                db.query(CrawlErrorLog)
                .filter(
                    CrawlErrorLog.chapter_url == chapter_url,
                    CrawlErrorLog.error_type == error_type,
                )
                .first()
            )

            if existing:
                # Increment retry count and update timestamp
                existing.retry_count = CrawlErrorLog.retry_count + 1
                existing.last_attempt = datetime.utcnow()
                existing.error_message = error_message or existing.error_message
                existing.resolved = 0  # Re-mark as unresolved
            else:
                # Create new error log
                error_log = CrawlErrorLog(
                    manga_id=manga_id,
                    chapter_id=chapter_id,
                    chapter_number=chapter_number,
                    chapter_url=chapter_url,
                    error_type=error_type,
                    error_message=error_message,
                    retry_count=0,
                    last_attempt=datetime.utcnow(),
                    resolved=0,
                )
                db.add(error_log)

            db.commit()
            logger.debug(
                "  Logged error for chapter %d: %s - %s",
                chapter_number,
                error_type,
                error_message or "",
            )
        except Exception as e:
            logger.warning(
                "  Failed to log error to DB: %s", e
            )
            db.rollback()

    def _mark_error_resolved(
        self,
        db: SessionLocal,
        chapter_url: str,
    ) -> None:
        """
        Mark all unresolved errors for a chapter URL as resolved.
        Called when a chapter is successfully crawled.

        Args:
            db: Database session.
            chapter_url: The chapter URL that was successfully crawled.
        """
        try:
            db.query(CrawlErrorLog).filter(
                CrawlErrorLog.chapter_url == chapter_url,
                CrawlErrorLog.resolved == 0,
            ).update(
                {
                    "resolved": 1,
                    "last_attempt": datetime.utcnow(),
                },
                synchronize_session=False,
            )
            db.commit()
        except Exception as e:
            logger.warning(
                "  Failed to mark errors as resolved: %s", e
            )
            db.rollback()

    def _retry_failed_chapters(
        self,
        manga: Manga,
        manga_slug: str,
        db: SessionLocal,
        max_retries: int = 3,
    ) -> dict:
        """
        Retry previously failed chapters for a manga.
        Only retries chapters that have been retried fewer than max_retries times.

        Args:
            manga: The Manga object.
            manga_slug: Slugified manga title.
            db: Database session.
            max_retries: Maximum number of retry attempts before giving up.

        Returns:
            Dict with retry stats: attempted, succeeded, images_downloaded, chapters_processed.
        """
        stats = {
            "attempted": 0,
            "succeeded": 0,
            "images_downloaded": 0,
            "chapters_processed": 0,
        }

        # Get unresolved errors for this manga, with retry_count < max_retries
        failed_chapters = (
            db.query(CrawlErrorLog)
            .filter(
                CrawlErrorLog.manga_id == manga.id,
                CrawlErrorLog.resolved == 0,
                CrawlErrorLog.retry_count < max_retries,
            )
            .order_by(CrawlErrorLog.last_attempt.asc())
            .all()
        )

        if not failed_chapters:
            return stats

        logger.info(
            "  Found %d failed chapters to retry for '%s'",
            len(failed_chapters),
            manga.title,
        )

        for error_log in failed_chapters:
            chap_num = error_log.chapter_number
            stats["attempted"] += 1

            logger.info(
                "  Retrying chapter %d (attempt %d/%d, last error: %s)",
                chap_num,
                error_log.retry_count + 1,
                max_retries,
                error_log.error_type,
            )

            try:
                result = self._crawl_chapter_by_number(
                    manga=manga,
                    manga_slug=manga_slug,
                    chapter_number=chap_num,
                    chapter_url=error_log.chapter_url,
                    db=db,
                )

                if result and result > 0:
                    stats["images_downloaded"] += result
                    stats["succeeded"] += 1
                    stats["chapters_processed"] += 1

                    # Mark error as resolved
                    self._mark_error_resolved(
                        db=db,
                        chapter_url=error_log.chapter_url,
                    )
                    logger.info(
                        "  Retry succeeded for chapter %d: downloaded %d images",
                        chap_num,
                        result,
                    )
                else:
                    # Still failing, increment retry count
                    error_log.retry_count = CrawlErrorLog.retry_count + 1
                    error_log.last_attempt = datetime.utcnow()
                    db.commit()
                    logger.warning(
                        "  Retry failed for chapter %d (still no images/redirect)",
                        chap_num,
                    )

            except Exception as e:
                logger.error(
                    "  Retry error for chapter %d: %s",
                    chap_num,
                    e,
                )
                # Increment retry count
                try:
                    error_log.retry_count = CrawlErrorLog.retry_count + 1
                    error_log.last_attempt = datetime.utcnow()
                    db.commit()
                except Exception:
                    db.rollback()

        logger.info(
            "  Retry stats for '%s': %d attempted, %d succeeded, %d images",
            manga.title,
            stats["attempted"],
            stats["succeeded"],
            stats["images_downloaded"],
        )

        return stats

    @staticmethod
    def _count_existing_images(chapter_dir: str) -> int:

        """Count existing images in a chapter directory."""
        if not os.path.isdir(chapter_dir):
            return 0
        try:
            files = [
                f
                for f in os.listdir(chapter_dir)
                if f.lower().endswith(
                    (".jpg", ".jpeg", ".png", ".gif", ".webp")
                )
            ]
            return len(files)
        except OSError:
            return 0

    @staticmethod
    def _get_extension(image_url: str) -> str:
        """Extract file extension from image URL."""
        clean_url = image_url.split("?")[0]
        _, ext = os.path.splitext(clean_url)
        if ext.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
            return ext
        return ".jpg"
