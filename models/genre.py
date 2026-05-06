"""
Genre model for the crawler database.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Table, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.session import Base


# Association table for many-to-many relationship between manga and genres
manga_genre = Table(
    "manga_genre",
    Base.metadata,
    Column("manga_id", UUID(as_uuid=True), ForeignKey("manga.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", Integer, ForeignKey("genre.id", ondelete="CASCADE"), primary_key=True),
)


class Genre(Base):
    """Represents a manga genre/category."""

    __tablename__ = "genre"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    mangas = relationship(
        "Manga",
        secondary=manga_genre,
        back_populates="genres",
    )

    def __repr__(self) -> str:
        return f"<Genre(id={self.id}, name='{self.name}')>"
