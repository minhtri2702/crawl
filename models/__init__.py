"""
Model imports for SQLAlchemy.
Import all models here so they are registered with Base.
"""

from models.manga import Manga
from models.chapter import Chapter, ChapterImage
from models.genre import Genre, manga_genre
from models.crawl_error_log import CrawlErrorLog

__all__ = [
    "Manga",
    "Chapter",
    "ChapterImage",
    "Genre",
    "manga_genre",
    "CrawlErrorLog",
]


