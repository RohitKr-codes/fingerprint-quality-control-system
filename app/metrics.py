"""
metrics.py
----------
The five fundamental biometric image-quality metrics used to gate a
contactless fingerprint capture:

    1. Blur          -> Laplacian variance          (< 10ms budget)
    2. Brightness    -> grayscale mean intensity      (< 5ms budget)
    3. Glare         -> over-saturation pixel ratio   (< 10ms budget)
    4. ROI           -> Otsu threshold + area ratio   (< 100ms budget)
    5. Ridge clarity -> Gabor filter response variance(< 150ms budget)

Every function accepts a BGR numpy array (as returned by utils.load_image)
and returns a small, JSON-serializable dict. Keeping each metric isolated
means they can be unit tested, re-tuned, or swapped out independently.
"""

import cv2
import numpy as np

from .config import DEFAULT_THRESHOLDS, PERFORMANCE_BUDGET_MS
from .utils import timed, to_grayscale


# --------------------------------------------------------------------------- #
# Metric 1: Blur Detection
# --------------------------------------------------------------------------- #

@timed(budget_ms=PERFORMANCE_BUDGET_MS["blur"])
def check_blur(image_bgr: np.ndarray, threshold: float = None) -> dict:
    """
    Detects motion/focus blur using the variance of the Laplacian operator.

    The Laplacian is the 2nd spatial derivative of pixel intensity; sharp
    edges produce large second-derivative swings (high variance), while a
    blurry image has smoothed-out transitions (low variance).

    Parameters
    ----------
    image_bgr : np.ndarray
        Input image in BGR color space.
    threshold : float, optional
        Minimum acceptable Laplacian variance. Defaults to config value.

    Returns
    -------
    dict: {"blur_score": float, "is_blurry": bool}
    """
    threshold = DEFAULT_THRESHOLDS.blur_min if threshold is None else threshold

    gray = to_grayscale(image_bgr)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    blur_score = float(laplacian.var())

    return {
        "blur_score": round(blur_score, 2),
        "is_blurry": blur_score < threshold,
    }


# --------------------------------------------------------------------------- #
# Metric 2: Brightness Assessment
# --------------------------------------------------------------------------- #

@timed(budget_ms=PERFORMANCE_BUDGET_MS["brightness"])
def check_brightness(
    image_bgr: np.ndarray,
    min_thresh: float = None,
    max_thresh: float = None,
) -> dict:
    """
    Measures average luminance to flag frames that are too dark or too
    bright to reliably reveal fingerprint ridges.

    Returns
    -------
    dict: {"brightness": float, "too_dark": bool, "too_bright": bool}
    """
    min_thresh = DEFAULT_THRESHOLDS.brightness_min if min_thresh is None else min_thresh
    max_thresh = DEFAULT_THRESHOLDS.brightness_max if max_thresh is None else max_thresh

    gray = to_grayscale(image_bgr)
    brightness = float(np.mean(gray))

    return {
        "brightness": round(brightness, 2),
        "too_dark": brightness < min_thresh,
        "too_bright": brightness > max_thresh,
    }


# --------------------------------------------------------------------------- #
# Metric 3: Glare Detection
# --------------------------------------------------------------------------- #

@timed(budget_ms=PERFORMANCE_BUDGET_MS["glare"])
def check_glare(
    image_bgr: np.ndarray,
    max_glare_ratio: float = None,
    pixel_cutoff: int = None,
) -> dict:
    """
    Counts near-saturated pixels (specular reflection off wet or oily skin)
    that wash out ridge detail.

    Returns
    -------
    dict: {"has_glare": bool, "glare_fraction": float}
    """
    max_glare_ratio = (
        DEFAULT_THRESHOLDS.glare_max_fraction if max_glare_ratio is None else max_glare_ratio
    )
    pixel_cutoff = (
        DEFAULT_THRESHOLDS.glare_pixel_cutoff if pixel_cutoff is None else pixel_cutoff
    )

    gray = to_grayscale(image_bgr)
    glare_pixels = int(np.sum(gray > pixel_cutoff))
    total_pixels = int(gray.size)
    glare_fraction = float(glare_pixels / total_pixels) if total_pixels else 0.0

    return {
        "glare_fraction": round(glare_fraction, 4),
        "has_glare": glare_fraction > max_glare_ratio,
    }


# --------------------------------------------------------------------------- #
# Metric 4: ROI (Region of Interest) Completeness
# --------------------------------------------------------------------------- #

@timed(budget_ms=PERFORMANCE_BUDGET_MS["roi"])
def check_roi_completeness(image_bgr: np.ndarray, min_roi_ratio: float = None) -> dict:
    """
    Segments the finger from the background using Gaussian blur + Otsu's
    binarization, then measures what fraction of the frame the finger
    actually occupies. A finger that's too far away or clipped by the
    frame edge produces a small ROI fraction.

    Returns
    -------
    dict: {"roi_fraction": float, "roi_complete": bool}
    """
    min_roi_ratio = (
        DEFAULT_THRESHOLDS.roi_min_fraction if min_roi_ratio is None else min_roi_ratio
    )

    gray = to_grayscale(image_bgr)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Otsu can invert foreground/background depending on lighting; assume the
    # smaller connected region is the finger and pick whichever binary mask
    # yields a more plausible (non-dominant) foreground area.
    foreground_pixels = int(np.sum(thresh > 0))
    total_pixels = int(gray.size)

    roi_fraction = float(foreground_pixels / total_pixels) if total_pixels else 0.0
    # If Otsu flagged more than half the image as "foreground", it likely
    # segmented the background instead -> invert the interpretation.
    if roi_fraction > 0.5:
        roi_fraction = 1.0 - roi_fraction

    return {
        "roi_fraction": round(roi_fraction, 4),
        "roi_complete": roi_fraction >= min_roi_ratio,
    }


# --------------------------------------------------------------------------- #
# Metric 5: Ridge Clarity
# --------------------------------------------------------------------------- #

@timed(budget_ms=PERFORMANCE_BUDGET_MS["ridge"])
def check_ridge_clarity(image_bgr: np.ndarray, threshold: float = None) -> dict:
    """
    Convolves the grayscale image with a bank of orientation-tuned Gabor
    kernels (matching typical fingerprint ridge frequency/orientation) and
    measures the response variance. Real ridge-valley patterns produce a
    strong, oscillating response; smooth skin or background clutter does
    not.

    Returns
    -------
    dict: {"ridge_score": float, "ridges_clear": bool}
    """
    threshold = DEFAULT_THRESHOLDS.ridge_min_score if threshold is None else threshold

    gray = to_grayscale(image_bgr)

    # Bank of 4 orientations captures ridges regardless of finger rotation.
    orientations = [0, np.pi / 4, np.pi / 2, 3 * np.pi / 4]
    responses = []

    for theta in orientations:
        kernel = cv2.getGaborKernel(
            ksize=(21, 21), sigma=5.0, theta=theta, lambd=10.0, gamma=0.5, psi=0
        )
        filtered = cv2.filter2D(gray, cv2.CV_64F, kernel)
        responses.append(np.var(filtered))

    ridge_score = float(max(responses) / 100.0)

    return {
        "ridge_score": round(ridge_score, 2),
        "ridges_clear": ridge_score >= threshold,
    }
