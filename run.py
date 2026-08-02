"""
run.py
------
Convenience entry point so the project can be launched with a single
command from the project root:

    python run.py

This simply shells out to `streamlit run ui/quality_app.py`, which is
the officially supported way to start a Streamlit app (Streamlit needs
its own process/runtime, so we can't just `import` and call it).
"""

import subprocess
import sys
from pathlib import Path


def main():
    project_root = Path(__file__).resolve().parent
    app_path = project_root / "ui" / "quality_app.py"

    if not app_path.exists():
        print(f"❌ Could not find {app_path}")
        sys.exit(1)

    print("🔒 Launching Fingerprint Quality Control System...")
    print(f"   -> streamlit run {app_path}")

    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path)]
    subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main()
