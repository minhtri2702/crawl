"""
Listing page crawler.
Scrapes manga data from the listing page (truyen-moi-cap-nhat).
"""

import logging
import re
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)

from utils.helpers import normalize_url, retry

logger = logging.getLogger(__name__)


class ListingCrawler:
    """
    Crawler for manga listing pages.
    Extracts manga title, detail URL, cover image URL, and latest chapter number.
    """

    def __init__(self, driver: WebDriver, base_url: str = "https://truyenqqno.com"):
        self.driver = driver
        self.base_url = base_url

    @retry(max_attempts=3, delay=5, backoff=2.0)
    def crawl_page(self, page_number: int) -> list[dict]:
        """
        Crawl a single listing page and extract manga data.

        Args:
            page_number: The page number to crawl.

        Returns:
            List of dicts with keys: title, url, cover_image_url, latest_chapter.
        """
        url = f"{self.base_url}/truyen-moi-cap-nhat/trang-{page_number}"
        logger.info("Crawling listing page: %s", url)

        self.driver.get(url)

        # Wait for the manga list to load
        manga_items = self._wait_for_manga_items()
        if not manga_items:
            logger.warning("No manga items found on page %d", page_number)
            return []

        results = []
        for item in manga_items:
            try:
                manga_data = self._extract_manga_data(item)
                if manga_data:
                    results.append(manga_data)
            except (NoSuchElementException, StaleElementReferenceException) as e:
                logger.warning("Error extracting manga data: %s", e)
                continue

        logger.info(
            "Extracted %d manga entries from page %d",
            len(results),
            page_number,
        )
        return results

    def _wait_for_manga_items(self) -> list:
        """Wait for manga items to load and return them."""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        try:
            # Try multiple possible selectors for manga list items
            selectors = [
                "ul.list_grid.grid li",
                "ul.list_grid li",
                "div.list_grid_out li",
                "div.list-stories li",
                "div.list-stories div.row",
                "div.story-list li",
                "div#story-list li",
                "ul.list-story li",
                "div.list-item li",
                "div.story-item",
                "div[class*='story'] li",
            ]

            for selector in selectors:
                try:
                    elements = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                    )
                    if elements:
                        logger.debug(
                            "Found %d manga items with selector: %s",
                            len(elements),
                            selector,
                        )
                        return elements
                except TimeoutException:
                    continue

            # Fallback: try to find any links that look like manga items
            logger.warning("Using fallback selector for manga items")
            return self.driver.find_elements(
                By.CSS_SELECTOR,
                "a[href*='/truyen-']",
            )

        except TimeoutException:
            logger.error("Timeout waiting for manga items to load")
            return []

    def _extract_manga_data(self, item) -> Optional[dict]:
        """
        Extract manga data from a single listing item element.

        Expected structure (truyenqqno.com):
        - Title: .book_name h3 a
        - URL: href from title link
        - Cover: .book_avatar img
        - Latest chapter: .last_chapter a
        """
        try:
            # Extract title and URL
            title_elem = None
            for selector in [
                ".book_name h3 a",
                "h3 a",
                "a[title]",
                ".story-name a",
                "a",
            ]:
                try:
                    title_elem = item.find_element(By.CSS_SELECTOR, selector)
                    if title_elem:
                        break
                except NoSuchElementException:
                    continue

            if not title_elem:
                return None

            title = title_elem.text.strip()
            manga_url = normalize_url(
                title_elem.get_attribute("href"), self.base_url
            )

            if not title:
                title = title_elem.get_attribute("title") or ""

            # Extract cover image
            cover_image_url = ""
            try:
                cover_img = item.find_element(By.CSS_SELECTOR, ".book_avatar img")
                cover_image_url = cover_img.get_attribute("src") or ""
                if not cover_image_url:
                    cover_image_url = cover_img.get_attribute("data-src") or ""
            except NoSuchElementException:
                try:
                    cover_img = item.find_element(By.CSS_SELECTOR, "img")
                    cover_image_url = cover_img.get_attribute("src") or ""
                    if not cover_image_url:
                        cover_image_url = cover_img.get_attribute("data-src") or ""
                except NoSuchElementException:
                    pass

            # Extract latest chapter
            latest_chapter = ""
            try:
                chapter_elem = item.find_element(By.CSS_SELECTOR, ".last_chapter a")
                latest_chapter = chapter_elem.text.strip()
            except NoSuchElementException:
                try:
                    chapter_elem = item.find_element(By.CSS_SELECTOR, ".chapter a")
                    latest_chapter = chapter_elem.text.strip()
                except NoSuchElementException:
                    pass

            if not title or not manga_url:
                return None

            return {
                "title": title,
                "url": manga_url,
                "cover_image_url": cover_image_url,
                "latest_chapter": latest_chapter,
            }

        except (NoSuchElementException, StaleElementReferenceException) as e:
            logger.warning("Failed to extract manga data: %s", e)
            return None

    def get_total_pages(self) -> int:
        """
        Get the total number of listing pages available.

        Returns:
            Total page count (defaults to 1 if not found).
        """
        try:
            pagination = self.driver.find_elements(
                By.CSS_SELECTOR, "div.pagination a, ul.pagination a, div.page a"
            )
            page_numbers = []
            for link in pagination:
                text = link.text.strip()
                if text.isdigit():
                    page_numbers.append(int(text))

            if page_numbers:
                return max(page_numbers)

            # Try to find last page link
            for link in pagination:
                href = link.get_attribute("href") or ""
                match = re.search(r"trang-(\d+)", href)
                if match:
                    page_numbers.append(int(match.group(1)))

            return max(page_numbers) if page_numbers else 1

        except Exception as e:
            logger.warning("Failed to get total pages: %s", e)
            return 1
