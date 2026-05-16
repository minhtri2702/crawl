"""
Detail page crawler.
Scrapes manga detail page for full metadata and chapter list.
"""

from __future__ import annotations

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

from utils.helpers import normalize_url, extract_chapter_number, retry, slugify

logger = logging.getLogger(__name__)


class DetailCrawler:
    """
    Crawler for manga detail pages.
    Extracts full manga metadata and chapter list.
    """

    def __init__(self, driver: WebDriver, base_url: str = "https://truyenqqno.com"):
        self.driver = driver
        self.base_url = base_url

    @retry(max_attempts=3, delay=5, backoff=2.0)
    def crawl_detail(self, url: str) -> Optional[dict]:
        """
        Crawl a manga detail page and extract all data.

        Args:
            url: The manga detail page URL.

        Returns:
            Dict with keys:
                - title
                - description
                - author
                - status
                - cover_image_url
                - alternative_titles
                - created_date
                - translation_team
                - age_rating
                - likes
                - followers
                - views
                - genres: list of genre names
                - chapters: list of dicts with chapter_number, chapter_name, url
            Returns None on failure.
        """
        logger.info("Crawling detail page: %s", url)

        try:
            self.driver.get(url)
        except TimeoutException:
            logger.warning("Timeout loading detail page: %s", url)
            return None

        try:
            # Wait for page content to load
            self._wait_for_content()

            # Extract manga metadata
            title = self._extract_title()
            if not title:
                logger.warning("Could not extract title from: %s", url)
                return None

            description = self._extract_description()
            author = self._extract_author()
            status = self._extract_status()
            cover_image_url = self._extract_cover_image()
            chapters = self._extract_chapters()

            # New fields
            alternative_titles = self._extract_alternative_titles()
            created_date = self._extract_created_date()
            translation_team = self._extract_translation_team()
            age_rating = self._extract_age_rating()
            likes = self._extract_likes()
            followers = self._extract_followers()
            views = self._extract_views()
            genres = self._extract_genres()

            logger.info(
                "Extracted detail for '%s': %d chapters, author=%s, status=%s, "
                "genres=%d, views=%s",
                title,
                len(chapters),
                author or "N/A",
                status or "N/A",
                len(genres),
                views or "N/A",
            )

            return {
                "title": title,
                "description": description,
                "author": author,
                "status": status,
                "cover_image_url": cover_image_url,
                "alternative_titles": alternative_titles,
                "created_date": created_date,
                "translation_team": translation_team,
                "age_rating": age_rating,
                "likes": likes,
                "followers": followers,
                "views": views,
                "genres": genres,
                "chapters": chapters,
            }

        except Exception as e:
            logger.error("Failed to crawl detail page %s: %s", url, e)
            return None

    def _wait_for_content(self) -> None:
        """Wait for the detail page content to load."""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        selectors = [
            "div.book_info",
            "div.story-detail",
            "div.detail-content",
            "div.story-info",
            "div.info",
            "h1",
            "div[class*='detail']",
        ]

        for selector in selectors:
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                return
            except TimeoutException:
                continue

        logger.warning("Could not find detail content container")

    def _extract_title(self) -> Optional[str]:
        """Extract manga title from the detail page."""
        selectors = [
            "div.book_other h1",
            "h1",
            "h1[class*='title']",
            "div[class*='title'] h1",
            "div.story-name h1",
            "div[class*='name'] h1",
            "meta[property='og:title']",
        ]

        for selector in selectors:
            try:
                if selector.startswith("meta"):
                    elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    return elem.get_attribute("content")
                elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                text = elem.text.strip()
                if text:
                    return text
            except NoSuchElementException:
                continue

        return None

    def _extract_description(self) -> Optional[str]:
        """Extract manga description/summary."""
        selectors = [
            "div.story-detail-info.detail-content",
            "div.story-detail p",
            "div.detail-content p",
            "div[class*='summary']",
            "div[class*='description']",
            "div[class*='content'] p",
            "meta[name='description']",
        ]

        for selector in selectors:
            try:
                if selector.startswith("meta"):
                    elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    return elem.get_attribute("content")
                elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                text = elem.text.strip()
                if text:
                    return text
            except NoSuchElementException:
                continue

        return None

    def _extract_author(self) -> Optional[str]:
        """Extract author name."""
        selectors = [
            "li.author a.org",
            "a[href*='tac-gia']",
            "a[href*='author']",
        ]

        for selector in selectors:
            try:
                elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                text = elem.text.strip()
                if text:
                    return text
            except NoSuchElementException:
                continue

        # Fallback: search for author in text
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            patterns = [
                r"Tác giả[:\s]+(.+?)(?:\n|$)",
                r"Author[:\s]+(.+?)(?:\n|$)",
            ]
            for pattern in patterns:
                match = re.search(pattern, body_text, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
        except NoSuchElementException:
            pass

        return None

    def _extract_status(self) -> Optional[str]:
        """Extract manga status (ongoing/completed)."""
        selectors = [
            "li.status p.col-xs-9",
            "span[class*='status']",
            "div[class*='status']",
        ]

        for selector in selectors:
            try:
                elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                text = elem.text.strip().lower()
                if "hoàn" in text or "full" in text or "completed" in text:
                    return "completed"
                if "đang" in text or "ongoing" in text or "on-going" in text:
                    return "ongoing"
                if text:
                    return text
            except NoSuchElementException:
                continue

        # Fallback: search for status in text
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            patterns = [
                r"Trạng thái[:\s]+(.+?)(?:\n|$)",
                r"Status[:\s]+(.+?)(?:\n|$)",
            ]
            for pattern in patterns:
                match = re.search(pattern, body_text, re.IGNORECASE)
                if match:
                    status_text = match.group(1).strip().lower()
                    if "hoàn" in status_text or "full" in status_text:
                        return "completed"
                    if "đang" in status_text or "ongoing" in status_text:
                        return "ongoing"
                    return status_text
        except NoSuchElementException:
            pass

        return None

    def _extract_cover_image(self) -> Optional[str]:
        """Extract cover image URL."""
        selectors = [
            "div.book_avatar img",
            "div[class*='cover'] img",
            "div[class*='image'] img",
            "div[class*='thumb'] img",
            "img[class*='cover']",
            "img[class*='thumb']",
            "meta[property='og:image']",
        ]

        for selector in selectors:
            try:
                if selector.startswith("meta"):
                    elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    return elem.get_attribute("content")
                elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                src = elem.get_attribute("src") or elem.get_attribute("data-src") or ""
                if src:
                    return src
            except NoSuchElementException:
                continue

        return None

    def _extract_alternative_titles(self) -> Optional[str]:
        """Extract alternative titles (Tên khác)."""
        try:
            elem = self.driver.find_element(
                By.CSS_SELECTOR, "li.othername p.other-name"
            )
            text = elem.text.strip()
            return text if text else None
        except NoSuchElementException:
            pass
        return None

    def _extract_created_date(self) -> Optional[str]:
        """Extract created date (Ngày tạo)."""
        try:
            # Find the list item that contains "Ngày tạo"
            list_items = self.driver.find_elements(By.CSS_SELECTOR, "ul.list-info li.row")
            for li in list_items:
                try:
                    label = li.find_element(By.CSS_SELECTOR, "p.name")
                    if "ngày tạo" in label.text.lower():
                        value = li.find_element(By.CSS_SELECTOR, "p.col-xs-9")
                        return value.text.strip()
                except NoSuchElementException:
                    continue
        except NoSuchElementException:
            pass
        return None

    def _extract_translation_team(self) -> Optional[str]:
        """Extract translation team (Nhóm dịch)."""
        try:
            elem = self.driver.find_element(
                By.CSS_SELECTOR, "li.team p.col-xs-9 a"
            )
            text = elem.text.strip()
            return text if text else None
        except NoSuchElementException:
            pass
        return None

    def _extract_age_rating(self) -> Optional[str]:
        """Extract age rating (Độ tuổi)."""
        try:
            list_items = self.driver.find_elements(By.CSS_SELECTOR, "ul.list-info li.row")
            for li in list_items:
                try:
                    label = li.find_element(By.CSS_SELECTOR, "p.name")
                    if "độ tuổi" in label.text.lower():
                        value = li.find_element(By.CSS_SELECTOR, "p.col-xs-9")
                        return value.text.strip()
                except NoSuchElementException:
                    continue
        except NoSuchElementException:
            pass
        return None

    def _extract_likes(self) -> Optional[int]:
        """Extract number of likes (Lượt thích)."""
        try:
            list_items = self.driver.find_elements(By.CSS_SELECTOR, "ul.list-info li.row")
            for li in list_items:
                try:
                    label = li.find_element(By.CSS_SELECTOR, "p.name")
                    if "lượt thích" in label.text.lower():
                        value = li.find_element(By.CSS_SELECTOR, "p.col-xs-9")
                        text = value.text.strip().replace(",", "").replace(".", "")
                        return int(text) if text.isdigit() else None
                except NoSuchElementException:
                    continue
        except NoSuchElementException:
            pass
        return None

    def _extract_followers(self) -> Optional[int]:
        """Extract number of followers (Lượt theo dõi)."""
        try:
            list_items = self.driver.find_elements(By.CSS_SELECTOR, "ul.list-info li.row")
            for li in list_items:
                try:
                    label = li.find_element(By.CSS_SELECTOR, "p.name")
                    if "theo dõi" in label.text.lower():
                        value = li.find_element(By.CSS_SELECTOR, "p.col-xs-9")
                        text = value.text.strip().replace(",", "").replace(".", "")
                        return int(text) if text.isdigit() else None
                except NoSuchElementException:
                    continue
        except NoSuchElementException:
            pass
        return None

    def _extract_views(self) -> Optional[int]:
        """Extract number of views (Lượt xem)."""
        try:
            list_items = self.driver.find_elements(By.CSS_SELECTOR, "ul.list-info li.row")
            for li in list_items:
                try:
                    label = li.find_element(By.CSS_SELECTOR, "p.name")
                    if "lượt xem" in label.text.lower():
                        value = li.find_element(By.CSS_SELECTOR, "p.col-xs-9")
                        text = value.text.strip().replace(",", "").replace(".", "")
                        return int(text) if text.isdigit() else None
                except NoSuchElementException:
                    continue
        except NoSuchElementException:
            pass
        return None

    def _extract_genres(self) -> list[str]:
        """Extract genre/category list."""
        genres = []
        try:
            genre_elements = self.driver.find_elements(
                By.CSS_SELECTOR, "ul.list01 li.li03 a"
            )
            for elem in genre_elements:
                try:
                    text = elem.text.strip()
                    if text:
                        genres.append(text)
                except NoSuchElementException:
                    continue
        except NoSuchElementException:
            pass
        return genres

    def _extract_chapters(self) -> list[dict]:
        """
        Extract chapter list from the detail page.

        Returns:
            List of dicts with keys: chapter_number, chapter_name, url.
        """
        chapters = []

        # Try to find chapter list container
        chapter_selectors = [
            "div.works-chapter-list a",
            "div.list_chapter a",
            "div.list-chapter a",
            "ul.list-chapter a",
            "div.chapter-list a",
            "ul.chapter-list a",
            "div#chapter-list a",
            "div[class*='chapter'] a",
            "ul[class*='chapter'] a",
        ]

        chapter_links = []
        for selector in chapter_selectors:
            try:
                links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if links:
                    chapter_links = links
                    logger.debug(
                        "Found %d chapter links with selector: %s",
                        len(links),
                        selector,
                    )
                    break
            except NoSuchElementException:
                continue

        if not chapter_links:
            logger.warning("No chapter links found on detail page")
            return []

        for link in chapter_links:
            try:
                chapter_url = normalize_url(
                    link.get_attribute("href"), self.base_url
                )
                chapter_text = link.text.strip()

                if not chapter_text:
                    continue

                chapter_number = extract_chapter_number(chapter_text)

                chapters.append({
                    "chapter_number": chapter_number,
                    "chapter_name": chapter_text,
                    "url": chapter_url,
                })
            except (NoSuchElementException, StaleElementReferenceException) as e:
                logger.warning("Error extracting chapter data: %s", e)
                continue

        # Sort chapters by number
        chapters.sort(key=lambda x: x["chapter_number"])

        return chapters
