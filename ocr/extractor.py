"""Text extraction from downloaded images via Tesseract OCR."""

from __future__ import annotations

from pathlib import Path

import pytesseract
from PIL import Image

from utils.exceptions import OCRError
from utils.logger import get_logger

logger = get_logger(__name__)


def extract_text(image_path: Path, tesseract_path: str) -> str:
    """Run OCR on an image file and return cleaned text. Raises OCRError on failure."""
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
    try:
        with Image.open(image_path) as img:
            raw_text = pytesseract.image_to_string(img)
    except FileNotFoundError as exc:
        raise OCRError(f"Image file not found: {image_path}") from exc
    except pytesseract.TesseractNotFoundError as exc:
        raise OCRError(f"Tesseract executable not found at '{tesseract_path}': {exc}") from exc
    except Exception as exc:  # pytesseract/Pillow surface various lib-specific errors
        raise OCRError(f"OCR failed for {image_path}: {exc}") from exc

    return _clean_text(raw_text)


def _clean_text(raw_text: str) -> str:
    """Collapse blank lines and trim whitespace from raw Tesseract output."""
    lines = [line.strip() for line in raw_text.splitlines()]
    non_empty = [line for line in lines if line]
    return "\n".join(non_empty)
