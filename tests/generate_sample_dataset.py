"""
tests/generate_sample_dataset.py
---------------------------------
Generates a synthetic 20-image placeholder dataset (5 good, 5 blurry,
5 dark, 5 glare) so the pipeline and batch tester can be exercised
immediately, without waiting on real phone captures.

IMPORTANT: These are synthetic ridge-pattern images for pipeline smoke
testing only. For the actual assignment submission (Part D), replace
these with 20 REAL phone-camera captures of your own fingertip, using
the same folder layout:

    dataset/good/*.jpg
    dataset/blurry/*.jpg
    dataset/dark/*.jpg
    dataset/glare/*.jpg

Usage (from project root):
    python tests/generate_sample_dataset.py
"""

import sys
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATASET_DIR = PROJECT_ROOT / "dataset"


def make_ridge_pattern(size=400, freq=0.35, angle_deg=15, noise=6):
    """Generate a synthetic finger-like ridge pattern using sinusoidal bands."""
    y, x = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
    theta = np.deg2rad(angle_deg)
    rot = x * np.cos(theta) + y * np.sin(theta)
    ridges = (np.sin(rot * freq) + 1) / 2.0  # 0..1
    ridges = (ridges * 255).astype(np.float32)

    # Elliptical vignette so the "finger" occupies a rounded region on a
    # neutral background, roughly emulating a fingertip silhouette.
    cy, cx = size / 2, size / 2
    ellipse_mask = (((x - cx) ** 2) / (size * 0.30) ** 2 + ((y - cy) ** 2) / (size * 0.42) ** 2) <= 1.0

    background = np.full((size, size), 200, dtype=np.float32)
    canvas = background.copy()
    canvas[ellipse_mask] = ridges[ellipse_mask]

    noise_arr = np.random.normal(0, noise, (size, size)).astype(np.float32)
    canvas = np.clip(canvas + noise_arr, 0, 255).astype(np.uint8)

    return cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR), ellipse_mask


def apply_blur(img, ksize=25):
    return cv2.GaussianBlur(img, (ksize, ksize), 0)


def apply_dark(img, factor=0.22):
    return np.clip(img.astype(np.float32) * factor, 0, 255).astype(np.uint8)


def apply_glare(img, mask, glare_strength=250, coverage=0.35):
    out = img.copy()
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return out
    n = int(len(ys) * coverage)
    idx = np.random.choice(len(ys), size=n, replace=False)
    for i in idx:
        cv2.circle(out, (xs[i], ys[i]), radius=3, color=(glare_strength,) * 3, thickness=-1)
    return out


def save(img, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img)


def generate():
    np.random.seed(42)
    categories = {
        "good": 5,
        "blurry": 5,
        "dark": 5,
        "glare": 5,
    }

    for category, count in categories.items():
        for i in range(1, count + 1):
            angle = np.random.uniform(0, 180)
            freq = np.random.uniform(0.28, 0.42)
            base, mask = make_ridge_pattern(angle_deg=angle, freq=freq)

            if category == "good":
                img = base
            elif category == "blurry":
                img = apply_blur(base, ksize=31)
            elif category == "dark":
                img = apply_dark(base, factor=0.18)
            elif category == "glare":
                img = apply_glare(base, mask, coverage=0.45)
            else:
                img = base

            prefix = "blur" if category == "blurry" else category
            out_path = DATASET_DIR / category / f"{prefix}_{i:02d}.jpg"
            save(img, out_path)
            print(f"Created {out_path.relative_to(PROJECT_ROOT)}")

    print("\n✅ Synthetic 20-image dataset generated under 'dataset/'.")
    print("   Replace with real phone captures before final submission.")


if __name__ == "__main__":
    generate()
