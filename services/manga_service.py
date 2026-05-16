"""
Manga service for database operations.
Handles CRUD operations for manga, chapters, and genres.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.manga import Manga
from models.chapter import Chapter
from models.genre import Genre, manga_genre
from utils.helpers import slugify

logger = logging.getLogger(__name__)


class MangaService:
    """Service class for manga and chapter database operations."""

    def __init__(self, db_session: Session):
        self.db = db_session

    def get_manga_by_url(self, url: str) -> Optional[Manga]:
        """Find a manga by its URL."""
        return self.db.query(Manga).filter(Manga.url == url).first()

    def get_chapter_by_url(self, url: str) -> Optional[Chapter]:
        """Find a chapter by its URL."""
        return self.db.query(Chapter).filter(Chapter.url == url).first()

    def get_existing_chapter_urls(self, manga_id: UUID) -> set:
        """Get set of existing chapter URLs for a manga."""
        chapters = (
            self.db.query(Chapter.url)
            .filter(Chapter.manga_id == manga_id)
            .all()
        )
        return {ch.url for ch in chapters}

    def get_or_create_genre(self, name: str) -> Genre:
        """Get an existing genre or create a new one."""
        genre_slug = slugify(name)
        genre = self.db.query(Genre).filter(Genre.slug == genre_slug).first()
        if not genre:
            genre = Genre(name=name, slug=genre_slug)
            self.db.add(genre)
            self.db.flush()
            logger.debug("Created new genre: %s", name)
        return genre

    def set_manga_genres(self, manga: Manga, genre_names: list[str]) -> None:
        """Set the genres for a manga."""
        if not genre_names:
            return
        genres = [self.get_or_create_genre(name) for name in genre_names]
        manga.genres = genres
        self.db.flush()

    def _get_next_stt(self) -> int:
        """Get the next STT (sequence number) for a new manga."""
        max_stt = self.db.query(Manga.stt).order_by(Manga.stt.desc()).first()
        if max_stt and max_stt[0] is not None:
            return max_stt[0] + 1
        return 1

    def create_manga(
        self,
        title: str,
        url: str,
        cover_image_path: Optional[str] = None,
        status: Optional[str] = None,
        description: Optional[str] = None,
        author: Optional[str] = None,
        alternative_titles: Optional[str] = None,
        created_date: Optional[str] = None,
        translation_team: Optional[str] = None,
        age_rating: Optional[str] = None,
        likes: Optional[int] = None,
        followers: Optional[int] = None,
        views: Optional[int] = None,
        genres: Optional[list[str]] = None,
    ) -> Manga:
        """Create a new manga entry."""
        next_stt = self._get_next_stt()
        manga = Manga(
            stt=next_stt,
            title=title,
            url=url,
            cover_image_path=cover_image_path,
            status=status,
            description=description,
            author=author,
            alternative_titles=alternative_titles,
            created_date=created_date,
            translation_team=translation_team,
            age_rating=age_rating,
            likes=likes,
            followers=followers,
            views=views,
        )
        self.db.add(manga)
        self.db.flush()

        # Set genres
        if genres:
            self.set_manga_genres(manga, genres)

        logger.info(
            "Created new manga: %s (ID: %s, STT: %d)",
            title, manga.id, manga.stt,
        )
        return manga

    def update_manga(
        self,
        manga: Manga,
        title: Optional[str] = None,
        cover_image_path: Optional[str] = None,
        status: Optional[str] = None,
        description: Optional[str] = None,
        author: Optional[str] = None,
        alternative_titles: Optional[str] = None,
        created_date: Optional[str] = None,
        translation_team: Optional[str] = None,
        age_rating: Optional[str] = None,
        likes: Optional[int] = None,
        followers: Optional[int] = None,
        views: Optional[int] = None,
        genres: Optional[list[str]] = None,
    ) -> Manga:
        """Update an existing manga entry."""
        if title is not None:
            manga.title = title
        if cover_image_path is not None:
            manga.cover_image_path = cover_image_path
        if status is not None:
            manga.status = status
        if description is not None:
            manga.description = description
        if author is not None:
            manga.author = author
        if alternative_titles is not None:
            manga.alternative_titles = alternative_titles
        if created_date is not None:
            manga.created_date = created_date
        if translation_team is not None:
            manga.translation_team = translation_team
        if age_rating is not None:
            manga.age_rating = age_rating
        if likes is not None:
            manga.likes = likes
        if followers is not None:
            manga.followers = followers
        if views is not None:
            manga.views = views
        if genres is not None:
            self.set_manga_genres(manga, genres)
        self.db.flush()
        logger.info("Updated manga: %s (ID: %s)", manga.title, manga.id)
        return manga

    def create_chapter(
        self,
        manga_id: UUID,
        chapter_number: float,
        chapter_name: str,
        url: str,
    ) -> Chapter:
        """Create a new chapter entry."""
        chapter = Chapter(
            manga_id=manga_id,
            chapter_number=chapter_number,
            chapter_name=chapter_name,
            url=url,
        )
        self.db.add(chapter)
        self.db.flush()
        logger.debug(
            "Created chapter %.1f for manga %s: %s",
            chapter_number,
            manga_id,
            chapter_name,
        )
        return chapter

    def get_all_existing_chapter_urls(self) -> set:
        """Get set of all existing chapter URLs across all manga."""
        chapters = self.db.query(Chapter.url).all()
        return {ch.url for ch in chapters}

    def bulk_create_chapters(
        self, manga_id: UUID, chapters_data: list[dict]
    ) -> list[Chapter]:
        """
        Bulk create chapters, skipping existing ones.

        Args:
            manga_id: The manga UUID.
            chapters_data: List of dicts with keys:
                chapter_number, chapter_name, url

        Returns:
            List of newly created Chapter objects.
        """
        # Check existing chapters for this manga
        existing_urls = self.get_existing_chapter_urls(manga_id)
        new_chapters = []

        for ch_data in chapters_data:
            if ch_data["url"] in existing_urls:
                logger.debug(
                    "Chapter already exists for manga %s, skipping: %s",
                    manga_id,
                    ch_data["url"],
                )
                continue

            try:
                chapter = self.create_chapter(
                    manga_id=manga_id,
                    chapter_number=ch_data["chapter_number"],
                    chapter_name=ch_data["chapter_name"],
                    url=ch_data["url"],
                )
                new_chapters.append(chapter)
                # Add to existing set to prevent duplicates within same batch
                existing_urls.add(ch_data["url"])
            except Exception as e:
                logger.warning(
                    "Failed to insert chapter '%s' for manga %s: %s. Skipping.",
                    ch_data.get("chapter_name", "unknown"),
                    manga_id,
                    e,
                )
                # Rollback to clear the failed transaction state.
                # The manga/genre data is still in the session's identity map
                # and will be re-persisted on next flush/commit.
                self.db.rollback()
                # Re-add manga/genre objects to session so they get re-persisted
                # on the next flush/commit
                continue

        if new_chapters:
            logger.info(
                "Added %d new chapters for manga %s",
                len(new_chapters),
                manga_id,
            )
        else:
            logger.info("No new chapters to add for manga %s", manga_id)

        return new_chapters

    def upsert_manga_with_chapters(
        self,
        manga_data: dict,
        chapters_data: list[dict],
    ) -> tuple[Manga, bool, int]:
        """
        Insert or update a manga and its chapters.

        Args:
            manga_data: Dict with keys: title, url, cover_image_path,
                       status, description, author, alternative_titles,
                       created_date, translation_team, age_rating, likes,
                       followers, views, genres
            chapters_data: List of dicts with keys: chapter_number,
                          chapter_name, url

        Returns:
            Tuple of (Manga, is_new, new_chapters_count)
        """
        existing_manga = self.get_manga_by_url(manga_data["url"])

        if existing_manga:
            # Update existing manga info
            self.update_manga(
                manga=existing_manga,
                title=manga_data.get("title"),
                cover_image_path=manga_data.get("cover_image_path"),
                status=manga_data.get("status"),
                description=manga_data.get("description"),
                author=manga_data.get("author"),
                alternative_titles=manga_data.get("alternative_titles"),
                created_date=manga_data.get("created_date"),
                translation_team=manga_data.get("translation_team"),
                age_rating=manga_data.get("age_rating"),
                likes=manga_data.get("likes"),
                followers=manga_data.get("followers"),
                views=manga_data.get("views"),
                genres=manga_data.get("genres"),
            )
            # Only insert new chapters
            new_chapters = self.bulk_create_chapters(
                existing_manga.id, chapters_data
            )
            self.db.commit()
            return existing_manga, False, len(new_chapters)
        else:
            # Create new manga (UUID and STT auto-generated)
            manga = self.create_manga(
                title=manga_data["title"],
                url=manga_data["url"],
                cover_image_path=manga_data.get("cover_image_path"),
                status=manga_data.get("status"),
                description=manga_data.get("description"),
                author=manga_data.get("author"),
                alternative_titles=manga_data.get("alternative_titles"),
                created_date=manga_data.get("created_date"),
                translation_team=manga_data.get("translation_team"),
                age_rating=manga_data.get("age_rating"),
                likes=manga_data.get("likes"),
                followers=manga_data.get("followers"),
                views=manga_data.get("views"),
                genres=manga_data.get("genres"),
            )
            # Insert all chapters
            new_chapters = self.bulk_create_chapters(manga.id, chapters_data)
            self.db.commit()
            return manga, True, len(new_chapters)
