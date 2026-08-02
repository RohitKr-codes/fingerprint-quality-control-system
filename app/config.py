"""
config.py
---------
Central configuration for the Fingerprint Quality Control System.

Every threshold, weight, and guidance string lives here so the rest of the
codebase never hardcodes a "magic number". The Streamlit UI reads and writes
these values live via sidebar sliders (see ui/quality_app.py), so keeping
them in one dataclass-like module makes the whole pipeline tunable without
touching the metric logic itself.
"""

from dataclasses import dataclass, field, asdict


# --------------------------------------------------------------------------- #
# 1. Hard Thresholds (reject / accept boundaries for each metric)
# --------------------------------------------------------------------------- #

@dataclass
class Thresholds:
    # Blur -> Laplacian variance. Below this = blurry.
    blur_min: float = 10.0

    # Brightness -> mean grayscale intensity (0-255).
    brightness_min: float = 50.0
    brightness_max: float = 210.0

    # Glare -> fraction of pixels with intensity > glare_pixel_cutoff.
    glare_pixel_cutoff: int = 240
    glare_max_fraction: float = 0.05

    # ROI -> fraction of frame occupied by the finger.
    roi_min_fraction: float = 0.15

    # Ridge clarity -> Gabor filter response variance score.
    ridge_min_score: float = 15.0

    # Composite score pass mark (0-100 scale).
    composite_pass_score: float = 60.0


# --------------------------------------------------------------------------- #
# 2. Normalization Reference Points (used to map raw metric -> 0..1 score)
# --------------------------------------------------------------------------- #

@dataclass
class NormalizationRefs:
    blur_reference: float = 100.0        # blur_score / blur_reference, capped at 1.0
    brightness_ideal: float = 128.0       # ideal mid-gray brightness target
    glare_reference: float = 0.05         # same as glare_max_fraction by default
    roi_reference: float = 0.30           # roi_fraction / roi_reference, capped at 1.0
    ridge_reference: float = 30.0         # ridge_score / ridge_reference, capped at 1.0


# --------------------------------------------------------------------------- #
# 3. Composite Score Weights (must sum to 1.0)
# --------------------------------------------------------------------------- #

@dataclass
class Weights:
    blur: float = 0.25
    brightness: float = 0.15
    glare: float = 0.15
    roi: float = 0.20
    ridge: float = 0.25

    def as_dict(self):
        return asdict(self)

    def total(self):
        return sum(self.as_dict().values())


# --------------------------------------------------------------------------- #
# 4. Performance Budget (milliseconds) - used by utils.timed() to flag
#    any stage that blows past its allotted budget in the console/logs.
# --------------------------------------------------------------------------- #

PERFORMANCE_BUDGET_MS = {
    "blur": 10,
    "brightness": 5,
    "glare": 10,
    "roi": 100,
    "ridge": 150,
    "total": 300,
}


# --------------------------------------------------------------------------- #
# 5. Guidance Messages - single source of truth for user-facing feedback
# --------------------------------------------------------------------------- #

GUIDANCE_MESSAGES = {
    "blurry": "Image is too blurry. Hold your camera steady and re-focus.",
    "too_dark": "Lighting is too dark. Turn on your flash or move to a lit area.",
    "too_bright": "Image is overexposed. Move away from direct bright light.",
    "glare": "Glare detected on finger. Tilt phone slightly to eliminate reflection.",
    "roi_incomplete": "Finger too far or incomplete. Move finger closer to fill the frame.",
    "ridge_unclear": "Ridge structure unclear. Clean camera lens or adjust lighting.",
    "pass": "Good capture — ready for processing.",
}


# --------------------------------------------------------------------------- #
# 6. Default instances (import these directly for convenience)
# --------------------------------------------------------------------------- #

DEFAULT_THRESHOLDS = Thresholds()
DEFAULT_NORMALIZATION = NormalizationRefs()
DEFAULT_WEIGHTS = Weights()


# --------------------------------------------------------------------------- #
# 7. App metadata (used in the Streamlit UI header / README generation)
# --------------------------------------------------------------------------- #

APP_NAME = "Fingerprint Quality Control System"
APP_TAGLINE = "Real-time contactless fingerprint capture quality gate"
APP_VERSION = "1.0.0"
