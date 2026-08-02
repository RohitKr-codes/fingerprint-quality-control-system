"""
utils.py
--------
Shared helper utilities used across the quality-control pipeline:

    - safe image loading (from a filesystem path OR raw bytes, e.g. an
      uploaded Streamlit file)
    - a `@timed` decorator that measures execution time in milliseconds
      and can flag a stage that blows its performance budget
    - lightweight logging setup that writes to outputs/logs/
"""

import functools
import logging
import os
import time
from pathlib import Path

import cv2
import numpy as np


# --------------------------------------------------------------------------- #
# Logging setup
# --------------------------------------------------------------------------- #

_LOG_DIR = Path(__file__).resolve().parent.parent / "outputs" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "qc_pipeline.log"

logger = logging.getLogger("fingerprint_qc")
logger.setLevel(logging.INFO)

if not logger.handlers:
    file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )
    logger.addHandler(file_handler)


# --------------------------------------------------------------------------- #
# Image loading
# --------------------------------------------------------------------------- #

def load_image(image_source) -> np.ndarray:
    """
    Load an image from any of the following:
        - a filesystem path (str or Path)
        - raw bytes (e.g. from Streamlit's `st.file_uploader().read()`)
        - an already-decoded numpy BGR array (passed straight through)

    Returns
    -------
    np.ndarray
        A BGR image array, ready for OpenCV processing.

    Raises
    ------
    ValueError
        If the image could not be decoded / does not exist.
    """
    # Already a numpy array -> assume it's a valid BGR image.
    if isinstance(image_source, np.ndarray):
        if image_source.size == 0:
            raise ValueError("Provided image array is empty.")
        return image_source

    # Raw bytes -> decode with OpenCV.
    if isinstance(image_source, (bytes, bytearray)):
        file_bytes = np.asarray(bytearray(image_source), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image bytes. File may be corrupted.")
        return img

    # Path-like -> read from disk.
    path = str(image_source)
    if not os.path.exists(path):
        raise ValueError(f"Image path does not exist: {path}")

    img = cv2.imread(path)
    if img is None:
        raise ValueError(f"OpenCV could not read image at: {path}")
    return img


# --------------------------------------------------------------------------- #
# Timing decorator
# --------------------------------------------------------------------------- #

def timed(budget_ms: float = None):
    """
    Decorator that measures a function's execution time in milliseconds and
    stashes it under the "_elapsed_ms" key of the returned dict (the metric
    functions all return dicts, so this composes cleanly).

    If `budget_ms` is provided and the function exceeds it, a warning is
    logged (useful for verifying the < 300ms total pipeline budget).
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000.0

            if isinstance(result, dict):
                result["_elapsed_ms"] = round(elapsed_ms, 3)

            if budget_ms is not None and elapsed_ms > budget_ms:
                logger.warning(
                    "%s exceeded budget: %.2fms > %.2fms",
                    func.__name__, elapsed_ms, budget_ms
                )
            return result

        return wrapper

    return decorator


# --------------------------------------------------------------------------- #
# Misc helpers
# --------------------------------------------------------------------------- #

def to_grayscale(image_bgr: np.ndarray) -> np.ndarray:
    """Convert a BGR image to grayscale, guarding against already-gray input."""
    if len(image_bgr.shape) == 2:
        return image_bgr
    return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp a value into the [lo, hi] range."""
    return max(lo, min(hi, value))


def ensure_dir(path) -> Path:
    """Create a directory (and parents) if it doesn't already exist."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
