"""
Manga model for the crawler database.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Text, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.session import Base


class Manga(Base):
    """Represents a manga entry in the database."""

    __tablename__ = "manga"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    stt = Column(
        Integer,
        unique=True,
        nullable=False,
    )
    title = Column(String(500), nullable=False, index=True)
    url = Column(String(1000), unique=True, nullable=False, index=True)
    cover_image_path = Column(String(1000), nullable=True)
    status = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    author = Column(String(255), nullable=True)
    alternative_titles = Column(Text, nullable=True)
    created_date = Column(String(50), nullable=True)
    translation_team = Column(String(255), nullable=True)
    age_rating = Column(String(50), nullable=True)
    likes = Column(BigInteger, nullable=True, default=0)
    followers = Column(BigInteger, nullable=True, default=0)
    views = Column(BigInteger, nullable=True, default=0)
    max_chapter_crawled = Column(
        Integer, nullable=True, default=0,
        comment="Highest chapter number that has been crawled for images"
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    chapters = relationship(
        "Chapter", back_populates="manga", cascade="all, delete-orphan"
    )

    genres = relationship(
        "Genre",
        secondary="manga_genre",
        back_populates="mangas",
    )

    def __repr__(self) -> str:
        return f"<Manga(id={self.id}, stt={self.stt}, title='{self.title}')>"
