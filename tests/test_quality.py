"""
tests/test_quality.py
----------------------
Batch evaluation script (Assignment Part D).

Runs `quality_gate()` over every image in `dataset/<category>/*` and prints
a summary table, then saves the full results to
`outputs/test_results.csv`.

Usage (from project root):
    python tests/test_quality.py
    python tests/test_quality.py --dataset dataset --out outputs/test_results.csv
"""

import argparse
import glob
import os
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.quality_assessment import quality_gate  # noqa: E402


EXPECTED_DEFECT = {
    "good": None,
    "blurry": "blurry",
    "dark": "too_dark",
    "glare": "glare",
}


def run_batch_tests(dataset_dir: str = "dataset", out_csv: str = "outputs/test_results.csv"):
    dataset_dir = str(PROJECT_ROOT / dataset_dir) if not os.path.isabs(dataset_dir) else dataset_dir
    out_csv = str(PROJECT_ROOT / out_csv) if not os.path.isabs(out_csv) else out_csv

    image_paths = sorted(
        p for p in glob.glob(f"{dataset_dir}/*/*.*")
        if p.lower().endswith((".jpg", ".jpeg", ".png"))
    )

    if not image_paths:
        print(f"⚠️  No images found under '{dataset_dir}/<category>/'.")
        print("    Run `python tests/generate_sample_dataset.py` to create a synthetic")
        print("    20-image test set (good / blurry / dark / glare), or drop in your")
        print("    own phone captures using the same folder structure.")
        return

    records = []
    correct = 0

    for path in image_paths:
        category = os.path.basename(os.path.dirname(path))
        filename = os.path.basename(path)

        try:
            res = quality_gate(path)
        except Exception as exc:  # noqa: BLE001
            print(f"❌ Failed to process {filename}: {exc}")
            continue

        expected_defect = EXPECTED_DEFECT.get(category)
        if expected_defect is None:
            detected_correctly = res["passed"]
        else:
            flags = {
                "blurry": res["blur"]["is_blurry"],
                "too_dark": res["brightness"]["too_dark"],
                "glare": res["glare"]["has_glare"],
            }
            detected_correctly = flags.get(expected_defect, False)

        correct += int(detected_correctly)

        records.append({
            "File": filename,
            "Expected Category": category,
            "Passed": res["passed"],
            "Composite Score": res["composite_score"],
            "Blur Score": res["blur"]["blur_score"],
            "Brightness": res["brightness"]["brightness"],
            "Glare Fraction": res["glare"]["glare_fraction"],
            "ROI Fraction": res["roi"]["roi_fraction"],
            "Ridge Score": res["ridge"]["ridge_score"],
            "Guidance": res["guidance"],
            "Correctly Detected": detected_correctly,
            "Latency (ms)": res["total_elapsed_ms"],
        })

    df = pd.DataFrame(records)

    print("\n================ QUALITY CONTROL BATCH EVALUATION ================\n")
    print(df.to_string(index=False))

    accuracy = (correct / len(records) * 100) if records else 0.0
    print(f"\nDetection accuracy: {correct}/{len(records)} ({accuracy:.1f}%)")
    print(f"Average pipeline latency: {df['Latency (ms)'].mean():.2f} ms\n")

    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    print(f"Full results saved to: {out_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch-test the fingerprint QC pipeline.")
    parser.add_argument("--dataset", default="dataset", help="Path to dataset root (default: dataset)")
    parser.add_argument("--out", default="outputs/test_results.csv", help="Output CSV path")
    args = parser.parse_args()

    run_batch_tests(args.dataset, args.out)
