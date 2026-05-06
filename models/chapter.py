"""
Chapter model for the crawler database.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.session import Base


class Chapter(Base):
    """Represents a chapter entry in the database."""

    __tablename__ = "chapter"

    id = Column(Integer, primary_key=True, autoincrement=True)
    manga_id = Column(
        UUID(as_uuid=True),
        ForeignKey("manga.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chapter_number = Column(Float, nullable=False)
    chapter_name = Column(String(500), nullable=True)
    url = Column(String(1000), unique=True, nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    manga = relationship("Manga", back_populates="chapters")
    images = relationship(
        "ChapterImage", back_populates="chapter", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Chapter(id={self.id}, manga_id={self.manga_id}, "
            f"number={self.chapter_number}, name='{self.chapter_name}')>"
        )


class ChapterImage(Base):
    """
    Represents an image within a chapter.
    Used in the next phase when crawling chapter detail pages.
    """

    __tablename__ = "chapter_image"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chapter_id = Column(
        Integer,
        ForeignKey("chapter.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_url = Column(String(2000), nullable=False)
    image_path = Column(String(1000), nullable=True)
    page_order = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    chapter = relationship("Chapter", back_populates="images")

    def __repr__(self) -> str:
        return (
            f"<ChapterImage(id={self.id}, chapter_id={self.chapter_id}, "
            f"page_order={self.page_order})>"
        )
