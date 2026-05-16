"""
Image service for downloading and storing cover images.
Images are uploaded directly to MinIO (no local storage).
Path on MinIO: {slug}/{slug}.{ext}
"""

from __future__ import annotations

import os
import logging
from typing import Optional

import requests

from utils.helpers import slugify
from services.minio_service import MinioService

logger = logging.getLogger(__name__)


class ImageService:
    """Service for downloading and managing cover images."""

    def __init__(self, base_path: str = "./data", minio_service: Optional[MinioService] = None):
        self.base_path = base_path
        self.minio = minio_service
        os.makedirs(self.base_path, exist_ok=True)

    def download_cover_image(self, image_url: str, title: str) -> Optional[str]:
        """
        Download a cover image and upload directly to MinIO.
        Does NOT save to local disk.

        Args:
            image_url: The URL of the cover image to download.
            title: The manga title used to generate the filename on MinIO.

        Returns:
            The MinIO object path (e.g. one-piece/one-piece.jpg),
            or None on failure.
        """
        if not image_url:
            logger.warning("No image URL provided for '%s'", title)
            return None

        if not self.minio:
            logger.warning("MinIO not configured, skipping cover download for '%s'", title)
            return None

        try:
            slug = slugify(title)
            ext = self._get_extension(image_url)
            minio_object = f"{slug}/{slug}{ext}"

            # Check if already exists on MinIO
            if self.minio.object_exists(minio_object):
                logger.info("Cover already exists on MinIO, skipping: %s", minio_object)
                return minio_object

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

            # Upload directly to MinIO from memory
            self.minio.upload_bytes(
                data=response.content,
                object_name=minio_object,
                content_type=f"image/{ext.lstrip('.')}",
            )
            logger.info("Cover uploaded to MinIO: %s", minio_object)

            return minio_object

        except requests.RequestException as e:
            logger.error(
                "Failed to download cover image '%s' for '%s': %s",
                image_url,
                title,
                e,
            )
            return None
        except Exception as e:
            logger.error(
                "Failed to upload cover for '%s': %s",
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
