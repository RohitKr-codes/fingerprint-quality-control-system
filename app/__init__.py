"""
Fingerprint Quality Control System
------------------------------------
Core application package containing the image-quality metric engine
used to gate contactless fingerprint captures before they are sent to
downstream biometric models (segmentation, minutiae extraction, matching).

Modules:
    config.py               -> All tunable thresholds, weights, and guidance text
    metrics.py               -> The 5 individual quality-metric functions
    quality_assessment.py    -> Normalization + composite scoring + quality_gate()
    utils.py                 -> Image I/O helpers, timing decorator, logging
"""

from .quality_assessment import quality_gate
from .metrics import (
    check_blur,
    check_brightness,
    check_glare,
    check_roi_completeness,
    check_ridge_clarity,
)

__all__ = [
    "quality_gate",
    "check_blur",
    "check_brightness",
    "check_glare",
    "check_roi_completeness",
    "check_ridge_clarity",
]

__version__ = "1.0.0"
