"""
Image service for downloading and storing cover images.
Images are stored in: data/{slug}/{slug}.{ext}
"""

import os
import logging
from typing import Optional

import requests

from utils.helpers import slugify

logger = logging.getLogger(__name__)


class ImageService:
    """Service for downloading and managing cover images."""

    def __init__(self, base_path: str = "./data"):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def download_cover_image(self, image_url: str, title: str) -> Optional[str]:
        """
        Download a cover image and save it to data/{slug}/{slug}.{ext}.

        Args:
            image_url: The URL of the cover image to download.
            title: The manga title used to generate the folder and filename.

        Returns:
            The relative path to the saved image (e.g. data/one-piece/one-piece.jpg),
            or None on failure.
        """
        if not image_url:
            logger.warning("No image URL provided for '%s'", title)
            return None

        try:
            slug = slugify(title)
            manga_dir = os.path.join(self.base_path, slug)
            os.makedirs(manga_dir, exist_ok=True)

            ext = self._get_extension(image_url)
            filename = f"{slug}{ext}"
            filepath = os.path.join(manga_dir, filename)

            # Skip if file already exists
            if os.path.exists(filepath):
                logger.info("Cover already exists, skipping: %s", filepath)
                return filepath

            # Download the image
            logger.info("Downloading cover image: %s", image_url)
            response = requests.get(
                image_url,
                timeout=30,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Referer": "https://truyenqqno.com/",
                    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
                },
                stream=True,
            )
            response.raise_for_status()

            # Save the image
            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info("Cover saved: %s", filepath)
            return filepath

        except requests.RequestException as e:
            logger.error(
                "Failed to download cover image '%s' for '%s': %s",
                image_url,
                title,
                e,
            )
            return None
        except OSError as e:
            logger.error(
                "Failed to save cover image for '%s': %s",
                title,
                e,
            )
            return None

    def get_manga_dir(self, title: str) -> str:
        """Get the manga directory path for a given title."""
        slug = slugify(title)
        manga_dir = os.path.join(self.base_path, slug)
        os.makedirs(manga_dir, exist_ok=True)
        return manga_dir

    def get_chapter_dir(self, title: str, chapter_number: float) -> str:
        """
        Get the chapter directory path.
        Used in the next phase for storing chapter images.
        Example: data/one-piece/chap-1/
        """
        manga_dir = self.get_manga_dir(title)
        chapter_dir = os.path.join(manga_dir, f"chap-{int(chapter_number)}")
        os.makedirs(chapter_dir, exist_ok=True)
        return chapter_dir

    @staticmethod
    def _get_extension(image_url: str) -> str:
        """
        Extract file extension from image URL.
        Defaults to .jpg if not determinable.
        """
        # Remove query parameters
        clean_url = image_url.split("?")[0]
        _, ext = os.path.splitext(clean_url)
        if ext.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
            return ext
        return ".jpg"
