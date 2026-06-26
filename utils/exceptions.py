"""Custom exception hierarchy used across the app.

Each layer (scraper, ocr, database, publisher) raises its own subclass so
callers (CLI commands, GUI worker threads) can catch precisely and log a
useful, typed error instead of letting the app crash.
"""


class AppError(Exception):
    """Base class for all application-specific errors."""


class ScraperError(AppError):
    """Raised for Instagram scraping failures (network, parsing, etc.)."""


class LoginRequiredError(ScraperError):
    """Raised when an account/profile cannot be fetched without authentication."""


class RateLimitError(ScraperError):
    """Raised when Instagram throttles or blocks requests."""


class DownloadError(ScraperError):
    """Raised when a post's media fails to download or is corrupt."""


class OCRError(AppError):
    """Raised when text extraction from an image fails."""


class DatabaseError(AppError):
    """Raised for SQLite connection, schema, or query failures."""


class ConfigError(AppError):
    """Raised for invalid or missing configuration."""
