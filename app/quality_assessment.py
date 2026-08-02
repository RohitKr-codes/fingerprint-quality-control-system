"""
quality_assessment.py
---------------------
The orchestration layer of the pipeline.

    1. Normalizes each of the 5 raw metric outputs onto a common [0, 1] scale.
    2. Combines them into a single weighted composite score (0-100).
    3. Runs the master `quality_gate()` function that ties everything
       together: runs all 5 metrics, computes the composite score, decides
       pass/fail, and returns a single human-readable guidance message.

This is the ONLY function the Streamlit UI and batch test script need to
call — everything else in `metrics.py` / `config.py` is an implementation
detail behind it.
"""

import time

from .config import (
    DEFAULT_THRESHOLDS,
    DEFAULT_NORMALIZATION,
    DEFAULT_WEIGHTS,
    GUIDANCE_MESSAGES,
    PERFORMANCE_BUDGET_MS,
)
from .metrics import (
    check_blur,
    check_brightness,
    check_glare,
    check_roi_completeness,
    check_ridge_clarity,
)
from .utils import load_image, clamp, logger


# --------------------------------------------------------------------------- #
# Normalization: raw metric value -> score in [0, 1]
# --------------------------------------------------------------------------- #

def normalize_blur(blur_score: float, ref: float = None) -> float:
    ref = DEFAULT_NORMALIZATION.blur_reference if ref is None else ref
    return clamp(blur_score / ref, 0.0, 1.0)


def normalize_brightness(brightness: float, ideal: float = None) -> float:
    ideal = DEFAULT_NORMALIZATION.brightness_ideal if ideal is None else ideal
    return clamp(1.0 - (abs(brightness - ideal) / ideal), 0.0, 1.0)


def normalize_glare(glare_fraction: float, ref: float = None) -> float:
    ref = DEFAULT_NORMALIZATION.glare_reference if ref is None else ref
    if ref <= 0:
        return 0.0
    return clamp(1.0 - (glare_fraction / ref), 0.0, 1.0)


def normalize_roi(roi_fraction: float, ref: float = None) -> float:
    ref = DEFAULT_NORMALIZATION.roi_reference if ref is None else ref
    if ref <= 0:
        return 0.0
    return clamp(roi_fraction / ref, 0.0, 1.0)


def normalize_ridge(ridge_score: float, ref: float = None) -> float:
    ref = DEFAULT_NORMALIZATION.ridge_reference if ref is None else ref
    if ref <= 0:
        return 0.0
    return clamp(ridge_score / ref, 0.0, 1.0)


# --------------------------------------------------------------------------- #
# Composite Score
# --------------------------------------------------------------------------- #

def compute_composite_score(
    blur_res: dict,
    bright_res: dict,
    glare_res: dict,
    roi_res: dict,
    ridge_res: dict,
    weights=None,
    normalization=None,
) -> float:
    """
    Combines the 5 normalized metric scores into a single weighted
    composite score on a 0-100 scale.
    """
    weights = DEFAULT_WEIGHTS if weights is None else weights
    normalization = DEFAULT_NORMALIZATION if normalization is None else normalization

    n_blur = normalize_blur(blur_res["blur_score"], normalization.blur_reference)
    n_bright = normalize_brightness(bright_res["brightness"], normalization.brightness_ideal)
    n_glare = normalize_glare(glare_res["glare_fraction"], normalization.glare_reference)
    n_roi = normalize_roi(roi_res["roi_fraction"], normalization.roi_reference)
    n_ridge = normalize_ridge(ridge_res["ridge_score"], normalization.ridge_reference)

    composite = (
        weights.blur * n_blur
        + weights.brightness * n_bright
        + weights.glare * n_glare
        + weights.roi * n_roi
        + weights.ridge * n_ridge
    ) * 100.0

    return round(composite, 1)


# --------------------------------------------------------------------------- #
# Guidance Resolution
# --------------------------------------------------------------------------- #

def resolve_guidance(blur_res, bright_res, glare_res, roi_res, ridge_res) -> str:
    """
    Priority-ordered guidance: return the message for the FIRST hard
    failure encountered, so the user always gets one clear, actionable
    instruction rather than a wall of simultaneous complaints.
    """
    if blur_res["is_blurry"]:
        return GUIDANCE_MESSAGES["blurry"]
    if bright_res["too_dark"]:
        return GUIDANCE_MESSAGES["too_dark"]
    if bright_res["too_bright"]:
        return GUIDANCE_MESSAGES["too_bright"]
    if glare_res["has_glare"]:
        return GUIDANCE_MESSAGES["glare"]
    if not roi_res["roi_complete"]:
        return GUIDANCE_MESSAGES["roi_incomplete"]
    if not ridge_res["ridges_clear"]:
        return GUIDANCE_MESSAGES["ridge_unclear"]
    return GUIDANCE_MESSAGES["pass"]


# --------------------------------------------------------------------------- #
# Master Quality Gate
# --------------------------------------------------------------------------- #

def quality_gate(
    image_source,
    thresholds=None,
    weights=None,
    normalization=None,
) -> dict:
    """
    Runs the full 5-metric quality control pipeline on a single image and
    returns a pass/fail verdict with a composite score and actionable
    guidance.

    Parameters
    ----------
    image_source : str | Path | bytes | np.ndarray
        A filesystem path, raw image bytes (e.g. from a Streamlit upload),
        or an already-decoded BGR numpy array.
    thresholds : config.Thresholds, optional
        Override the default hard-reject thresholds (used by the UI sliders).
    weights : config.Weights, optional
        Override the default composite-score weighting.
    normalization : config.NormalizationRefs, optional
        Override the default normalization reference points.

    Returns
    -------
    dict
        {
            "passed": bool,
            "composite_score": float,
            "blur": {...}, "brightness": {...}, "glare": {...},
            "roi": {...}, "ridge": {...},
            "guidance": str,
            "total_elapsed_ms": float,
        }
    """
    thresholds = DEFAULT_THRESHOLDS if thresholds is None else thresholds
    start = time.perf_counter()

    img = load_image(image_source)

    blur_res = check_blur(img, threshold=thresholds.blur_min)
    bright_res = check_brightness(
        img, min_thresh=thresholds.brightness_min, max_thresh=thresholds.brightness_max
    )
    glare_res = check_glare(
        img, max_glare_ratio=thresholds.glare_max_fraction, pixel_cutoff=thresholds.glare_pixel_cutoff
    )
    roi_res = check_roi_completeness(img, min_roi_ratio=thresholds.roi_min_fraction)
    ridge_res = check_ridge_clarity(img, threshold=thresholds.ridge_min_score)

    composite_score = compute_composite_score(
        blur_res, bright_res, glare_res, roi_res, ridge_res,
        weights=weights, normalization=normalization,
    )

    has_hard_failure = (
        blur_res["is_blurry"]
        or bright_res["too_dark"]
        or bright_res["too_bright"]
        or glare_res["has_glare"]
        or not roi_res["roi_complete"]
        or not ridge_res["ridges_clear"]
    )

    passed = (composite_score >= thresholds.composite_pass_score) and (not has_hard_failure)

    guidance = resolve_guidance(blur_res, bright_res, glare_res, roi_res, ridge_res)

    total_elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
    if total_elapsed_ms > PERFORMANCE_BUDGET_MS["total"]:
        logger.warning(
            "quality_gate exceeded total budget: %.2fms > %dms",
            total_elapsed_ms, PERFORMANCE_BUDGET_MS["total"]
        )

    result = {
        "passed": passed,
        "composite_score": composite_score,
        "blur": blur_res,
        "brightness": bright_res,
        "glare": glare_res,
        "roi": roi_res,
        "ridge": ridge_res,
        "guidance": guidance,
        "total_elapsed_ms": total_elapsed_ms,
    }

    logger.info(
        "quality_gate | passed=%s score=%.1f elapsed=%.2fms guidance=%s",
        passed, composite_score, total_elapsed_ms, guidance
    )

    return result
