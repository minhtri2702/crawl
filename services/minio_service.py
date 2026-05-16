"""
MinIO service for uploading images to MinIO object storage.
Connects to MinIO server and provides upload/delete operations.
"""

from __future__ import annotations

import os
import io
import logging
from typing import Optional

from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)


class MinioService:
    """Service for uploading images to MinIO object storage."""

    def __init__(
        self,
        endpoint: str = None,
        access_key: str = None,
        secret_key: str = None,
        bucket_name: str = None,
        secure: bool = False,
    ):
        """
        Initialize MinIO client.

        Args:
            endpoint: MinIO server endpoint (e.g., "100.94.58.103:9000")
            access_key: MinIO access key
            secret_key: MinIO secret key
            bucket_name: Default bucket name to use
            secure: Use HTTPS (default: False for local/dev)
        """
        self.endpoint = endpoint or os.getenv("MINIO_ENDPOINT", "100.94.58.103:9000")
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.bucket_name = bucket_name or os.getenv("MINIO_BUCKET", "manga-images")
        self.secure = secure or os.getenv("MINIO_SECURE", "false").lower() == "true"

        self.client = Minio(
            endpoint=self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )

        # Ensure bucket exists
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Create the bucket if it doesn't exist."""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info("Created MinIO bucket: %s", self.bucket_name)
            else:
                logger.debug("MinIO bucket already exists: %s", self.bucket_name)
        except S3Error as e:
            logger.error("Failed to ensure MinIO bucket '%s': %s", self.bucket_name, e)
            raise

    def upload_file(
        self,
        local_file_path: str,
        object_name: str = None,
        bucket_name: str = None,
        content_type: str = "image/jpeg",
    ) -> Optional[str]:
        """
        Upload a local file to MinIO.

        Args:
            local_file_path: Path to the local file.
            object_name: Object name in MinIO. If None, uses the filename.
            bucket_name: Bucket to upload to. If None, uses default bucket.
            content_type: MIME type of the file.

        Returns:
            The object name in MinIO if successful, None otherwise.
        """
        if not os.path.exists(local_file_path):
            logger.warning("File not found: %s", local_file_path)
            return None

        bucket = bucket_name or self.bucket_name
        obj_name = object_name or local_file_path.replace("\\", "/")

        try:
            # Detect content type from file extension
            ext = os.path.splitext(local_file_path)[1].lower()
            mime_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
                ".bmp": "image/bmp",
            }
            content_type = mime_map.get(ext, content_type)

            file_size = os.path.getsize(local_file_path)
            self.client.fput_object(
                bucket_name=bucket,
                object_name=obj_name,
                file_path=local_file_path,
                content_type=content_type,
            )
            logger.debug(
                "Uploaded to MinIO: %s/%s (%d bytes)",
                bucket,
                obj_name,
                file_size,
            )
            return obj_name

        except S3Error as e:
            logger.error(
                "Failed to upload to MinIO: %s/%s - %s",
                bucket,
                obj_name,
                e,
            )
            return None

    def upload_bytes(
        self,
        data: bytes,
        object_name: str,
        bucket_name: str = None,
        content_type: str = "image/jpeg",
    ) -> Optional[str]:
        """
        Upload bytes directly to MinIO.

        Args:
            data: The image data as bytes.
            object_name: Object name in MinIO.
            bucket_name: Bucket to upload to. If None, uses default bucket.
            content_type: MIME type of the file.

        Returns:
            The object name in MinIO if successful, None otherwise.
        """
        bucket = bucket_name or self.bucket_name

        try:
            data_stream = io.BytesIO(data)
            data_stream.seek(0)

            self.client.put_object(
                bucket_name=bucket,
                object_name=object_name,
                data=data_stream,
                length=len(data),
                content_type=content_type,
            )
            logger.debug(
                "Uploaded bytes to MinIO: %s/%s (%d bytes)",
                bucket,
                object_name,
                len(data),
            )
            return object_name

        except S3Error as e:
            logger.error(
                "Failed to upload bytes to MinIO: %s/%s - %s",
                bucket,
                object_name,
                e,
            )
            return None

    def get_public_url(self, object_name: str, bucket_name: str = None) -> str:
        """
        Get the public URL for an object.

        Args:
            object_name: Object name in MinIO.
            bucket_name: Bucket name. If None, uses default bucket.

        Returns:
            The public URL string.
        """
        bucket = bucket_name or self.bucket_name
        # MinIO API endpoint for direct access
        # e.g., http://100.94.58.103:9000/manga-images/path/to/image.jpg
        protocol = "https" if self.secure else "http"
        return f"{protocol}://{self.endpoint}/{bucket}/{object_name}"

    def object_exists(self, object_name: str, bucket_name: str = None) -> bool:
        """
        Check if an object exists in MinIO.

        Args:
            object_name: Object name in MinIO.
            bucket_name: Bucket name. If None, uses default bucket.

        Returns:
            True if object exists, False otherwise.
        """
        bucket = bucket_name or self.bucket_name
        try:
            self.client.stat_object(bucket, object_name)
            return True
        except S3Error:
            return False

    def remove_object(self, object_name: str, bucket_name: str = None) -> bool:
        """
        Remove an object from MinIO.

        Args:
            object_name: Object name in MinIO.
            bucket_name: Bucket name. If None, uses default bucket.

        Returns:
            True if removed successfully, False otherwise.
        """
        bucket = bucket_name or self.bucket_name
        try:
            self.client.remove_object(bucket, object_name)
            logger.debug("Removed from MinIO: %s/%s", bucket, object_name)
            return True
        except S3Error as e:
            logger.error(
                "Failed to remove from MinIO: %s/%s - %s",
                bucket,
                object_name,
                e,
            )
            return False
