"""
Utility helper functions for the crawler.
"""

import re
import time
import logging
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)


# Vietnamese character mapping for slugification
VIETNAMESE_MAP = {
    "à": "a", "á": "a", "ạ": "a", "ả": "a", "ã": "a",
    "â": "a", "ầ": "a", "ấ": "a", "ậ": "a", "ẩ": "a", "ẫ": "a",
    "ă": "a", "ằ": "a", "ắ": "a", "ặ": "a", "ẳ": "a", "ẵ": "a",
    "è": "e", "é": "e", "ẹ": "e", "ẻ": "e", "ẽ": "e",
    "ê": "e", "ề": "e", "ế": "e", "ệ": "e", "ể": "e", "ễ": "e",
    "ì": "i", "í": "i", "ị": "i", "ỉ": "i", "ĩ": "i",
    "ò": "o", "ó": "o", "ọ": "o", "ỏ": "o", "õ": "o",
    "ô": "o", "ồ": "o", "ố": "o", "ộ": "o", "ổ": "o", "ỗ": "o",
    "ơ": "o", "ờ": "o", "ớ": "o", "ợ": "o", "ở": "o", "ỡ": "o",
    "ù": "u", "ú": "u", "ụ": "u", "ủ": "u", "ũ": "u",
    "ư": "u", "ừ": "u", "ứ": "u", "ự": "u", "ử": "u", "ữ": "u",
    "ỳ": "y", "ý": "y", "ỵ": "y", "ỷ": "y", "ỹ": "y",
    "đ": "d",
    # Uppercase
    "À": "A", "Á": "A", "Ạ": "A", "Ả": "A", "Ã": "A",
    "Â": "A", "Ầ": "A", "Ấ": "A", "Ậ": "A", "Ẩ": "A", "Ẫ": "A",
    "Ă": "A", "Ằ": "A", "Ắ": "A", "Ặ": "A", "Ẳ": "A", "Ẵ": "A",
    "È": "E", "É": "E", "Ẹ": "E", "Ẻ": "E", "Ẽ": "E",
    "Ê": "E", "Ề": "E", "Ế": "E", "Ệ": "E", "Ể": "E", "Ễ": "E",
    "Ì": "I", "Í": "I", "Ị": "I", "Ỉ": "I", "Ĩ": "I",
    "Ò": "O", "Ó": "O", "Ọ": "O", "Ỏ": "O", "Õ": "O",
    "Ô": "O", "Ồ": "O", "Ố": "O", "Ộ": "O", "Ổ": "O", "Ỗ": "O",
    "Ơ": "O", "Ờ": "O", "Ớ": "O", "Ợ": "O", "Ở": "O", "Ỡ": "O",
    "Ù": "U", "Ú": "U", "Ụ": "U", "Ủ": "U", "Ũ": "U",
    "Ư": "U", "Ừ": "U", "Ứ": "U", "Ự": "U", "Ử": "U", "Ữ": "U",
    "Ỳ": "Y", "Ý": "Y", "Ỵ": "Y", "Ỷ": "Y", "Ỹ": "Y",
    "Đ": "D",
}


def remove_vietnamese_diacritics(text: str) -> str:
    """Remove Vietnamese diacritics from text."""
    for viet_char, ascii_char in VIETNAMESE_MAP.items():
        text = text.replace(viet_char, ascii_char)
    return text


def slugify(text: str) -> str:
    """
    Convert text to a URL-friendly slug.
    Removes Vietnamese diacritics and special characters.
    Example: "Một Mình Ta" -> "mot-minh-ta"
    """
    # First remove Vietnamese diacritics
    text = remove_vietnamese_diacritics(text)
    text = text.lower().strip()
    # Remove any remaining non-alphanumeric characters (except spaces and hyphens)
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def retry(
    max_attempts: int = 3,
    delay: float = 5.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """
    Decorator that retries a function on failure with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts.
        delay: Initial delay between retries in seconds.
        backoff: Multiplier for delay after each retry.
        exceptions: Tuple of exceptions to catch.

    Returns:
        Decorated function.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.warning(
                            "Attempt %d/%d failed for %s: %s. "
                            "Retrying in %.1f seconds...",
                            attempt,
                            max_attempts,
                            func.__name__,
                            e,
                            current_delay,
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            "All %d attempts failed for %s: %s",
                            max_attempts,
                            func.__name__,
                            e,
                        )

            raise last_exception  # type: ignore

        return wrapper

    return decorator


def extract_chapter_number(chapter_text: str) -> float:
    """
    Extract chapter number from text like 'Chapter 1' or 'Chương 1'.
    Returns 0.0 if no number found.
    """
    match = re.search(r"(\d+(?:\.\d+)?)", chapter_text)
    if match:
        return float(match.group(1))
    return 0.0


def normalize_url(url: str, base_url: str = "https://truyenqqno.com") -> str:
    """
    Normalize a URL, prepending base URL if relative.
    """
    if url.startswith("http"):
        return url
    if url.startswith("/"):
        return f"{base_url}{url}"
    return f"{base_url}/{url}"
