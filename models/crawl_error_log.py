"""
CrawlErrorLog model.
Tracks failed chapter/image crawls for retry in subsequent runs.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, UniqueConstraint

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.session import Base


class CrawlErrorLog(Base):
    """
    Logs errors during chapter image crawling.
    Used to retry failed chapters in subsequent crawl runs.
    """

    __tablename__ = "crawl_error_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    manga_id = Column(
        UUID(as_uuid=True),
        ForeignKey("manga.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chapter_id = Column(
        Integer,
        ForeignKey("chapter.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    chapter_number = Column(Integer, nullable=False)
    chapter_url = Column(Text, nullable=False)
    error_type = Column(
        String(50),
        nullable=False,
        comment="Error type: redirect, timeout, no_images, download_failed, etc.",
    )
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    last_attempt = Column(DateTime, nullable=False, default=datetime.utcnow)
    resolved = Column(Integer, nullable=False, default=0, comment="0=unresolved, 1=resolved")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    manga = relationship("Manga", backref="crawl_errors")
    chapter = relationship("Chapter", backref="crawl_errors")

    __table_args__ = (
        UniqueConstraint(
            "chapter_url",
            "error_type",
            name="uq_chapter_url_error_type",
        ),
    )

    def __repr__(self):
        return (
            f"<CrawlErrorLog(chapter={self.chapter_number}, "
            f"type={self.error_type}, retry={self.retry_count})>"
        )
