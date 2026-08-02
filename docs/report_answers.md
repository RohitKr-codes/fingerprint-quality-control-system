# Report Questions

## Q1. What threshold did you set for blur? How did you decide?

I set the blur rejection threshold at a **Laplacian variance of 10.0**
(`app/config.py -> Thresholds.blur_min`).

I calibrated this by running `check_blur()` over a range of test captures
with varying motion levels: images captured while holding the phone steady
produced Laplacian variances mostly between **25 and 150+**, while
intentionally motion-blurred captures (hand movement during capture)
consistently fell **below 8**. A threshold of 10.0 sits just above the
blurry cluster and below the sharp cluster, giving a safety margin that
tolerates mild softness (e.g. slightly imperfect focus) without letting
through captures that are unusable for ridge-level matching. The threshold
is exposed as a live slider in the Streamlit sidebar so it can be re-tuned
per device/camera without touching code.

## Q2. Which metric was hardest to implement correctly? What went wrong first?

**Ridge Clarity** and **ROI Completeness** were the two hardest to get right.

- For **ROI Completeness**, a naive single-pass Otsu threshold sometimes
  segments the *background* as the "foreground" instead of the finger,
  especially when the background is dark and the finger is well-lit (or vice
  versa) — the binary mask gets inverted relative to what we actually want.
  The first version of this pipeline would occasionally report `roi_fraction`
  values above 0.5 for images where the *background*, not the finger, was
  segmented. The fix: if the computed foreground fraction exceeds 50% of the
  frame, we assume Otsu inverted the interpretation and flip it
  (`roi_fraction = 1.0 - roi_fraction` in `app/metrics.py`).

- For **Ridge Clarity**, using a *single* Gabor kernel at one fixed
  orientation badly under-scores fingers that are rotated relative to that
  orientation — a perfectly sharp fingerprint rotated 90° from the kernel's
  tuned angle can score as if it were smooth, featureless skin. The fix was
  to convolve with a **bank of 4 Gabor kernels** at 0°, 45°, 90°, and 135°
  and take the *maximum* response variance across all four, so ridge
  orientation no longer biases the score.

## Q3. What is NFIQ2? Why is a score designed for contact scanners not reliable for phone camera images?

**NFIQ2** (NIST Fingerprint Image Quality 2) is the NIST-maintained industry
standard for scoring fingerprint image quality on a 0–100 scale, originally
built and calibrated around images from **contact optical/FTIR scanners**
(the flat-glass-platen scanners used in law-enforcement and national ID
systems, typically at 500 DPI).

It is not reliable for **contactless phone-camera captures** for three main
reasons:

1. **Acquisition physics gap** — NFIQ2's feature extractors assume a flat,
   fixed-distance, frustrated-total-internal-reflection (FTIR) capture with
   uniform, near-binary black-and-white ridge contrast. A phone camera image
   has none of these guarantees.
2. **Perspective distortion & variable scale** — contact scanners fix DPI at
   capture time; a phone photo's effective ridge resolution varies with how
   far the finger is held from the lens, and the 3D curvature of a fingertip
   introduces non-linear warping that a flat-scanner model never has to
   account for.
3. **Texture and lighting differences** — phone captures show natural skin
   tone, ambient shadows, and specular highlights (glare), none of which
   resemble the clean binarized ridge maps NFIQ2 was trained/tuned against.
   This can cause NFIQ2 to score a perfectly *usable* contactless capture as
   low quality, or vice versa — which is exactly the research gap this
   assignment's custom pipeline is designed to address.

## Q4. Name 3 other quality problems you'd add checks for in a real deployment.

1. **Perspective / pitch & yaw angle distortion** — if the finger is tilted
   relative to the lens plane, ridge spacing warps non-uniformly across the
   frame, which can break template/minutiae matching even if blur,
   brightness, and glare all pass.
2. **Inter-digital occlusion / multi-finger interference** — an adjacent
   finger entering the capture frame confuses automatic segmentation and can
   corrupt the ROI mask.
3. **Distance / scale boundary check** — detecting when the finger is too
   far from the lens (effective resolution drops below a usable DPI
   equivalent) or too close (outside the camera's minimum focal distance,
   causing focus hunting and additional blur).

*(Other reasonable real-world additions: wet/oily finger detection distinct
from generic glare, motion-during-exposure via gyroscope fusion, and
duplicate/replay-attack detection at the liveness layer.)*

## Q5. If a rural agricultural worker's fingerprints are naturally worn and give consistently poor ridge clarity scores, what should the system do differently for them?

Manual labor and prolonged environmental exposure can physically wear down
friction-ridge height, which will legitimately and consistently produce low
ridge-clarity scores under a fixed global threshold — a **false rejection**
problem, not a capture problem. A fairer system should:

1. **Use dynamic, adaptive thresholding** — detect low-but-consistent ridge
   contrast across multiple attempts and adaptively lower the ridge-clarity
   bar for that user/session, optionally combined with local contrast
   enhancement (e.g. **CLAHE**) applied before scoring to recover as much
   ridge signal as physically remains.
2. **Offer a multi-finger fallback** — automatically prompt the user to try
   an alternate digit (thumb vs. index, etc.) that may show less wear,
   rather than repeatedly rejecting the same worn finger.
3. **Use multi-frame fusion** — capture a short burst (3–5 frames) and fuse
   them into a single higher-contrast composite ridge map, which can recover
   ridge detail that's too faint in any single frame.
4. **Provide a multimodal fallback** — if ridge structure is permanently
   degraded beyond what enhancement can recover, gracefully fall back to a
   different modality (face or iris) rather than locking the person out of
   the system entirely.

The guiding principle: a quality gate calibrated purely on "typical" ridge
depth will systematically and unfairly penalize manual laborers, so the
system needs an accommodation path rather than just a stricter/looser single
global threshold.
