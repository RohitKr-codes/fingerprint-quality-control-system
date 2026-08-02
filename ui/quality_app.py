"""
quality_app.py
--------------
Streamlit dashboard for the Fingerprint Quality Control System.

Run with (from project root):
    streamlit run ui/quality_app.py
or simply:
    python run.py

Features
--------
- Drag-and-drop image upload
- Live sidebar sliders for every QC threshold (no hardcoded values)
- Animated composite-score ring + count-up number
- Five metric cards, each with a PASS/FAIL badge and animated progress bar
- A single, prioritized guidance banner telling the user exactly what to fix
- A confetti burst when a capture passes, for a little delight
"""

import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# --------------------------------------------------------------------------- #
# Make the `app` package importable whether Streamlit is launched from the
# project root or from inside ui/.
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import (  # noqa: E402
    Thresholds, Weights, NormalizationRefs,
    DEFAULT_THRESHOLDS, DEFAULT_WEIGHTS, DEFAULT_NORMALIZATION,
    APP_NAME, APP_TAGLINE, APP_VERSION,
)
from app.quality_assessment import quality_gate  # noqa: E402


# --------------------------------------------------------------------------- #
# Page setup
# --------------------------------------------------------------------------- #

st.set_page_config(
    page_title="Fingerprint QC Gate",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="expanded",
)

UI_DIR = Path(__file__).resolve().parent
CSS_PATH = UI_DIR / "css" / "style.css"
JS_PATH = UI_DIR / "js" / "animations.js"


def load_css():
    css = CSS_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def load_js_source() -> str:
    return JS_PATH.read_text(encoding="utf-8")


load_css()


# --------------------------------------------------------------------------- #
# Hero header
# --------------------------------------------------------------------------- #

st.markdown(
    f"""
    <div class="qc-hero">
        <h1>🔒 {APP_NAME}</h1>
        <p>{APP_TAGLINE} — five biometric checks, one composite score, real-time capture guidance.</p>
        <div class="qc-badge-row">
            <span class="qc-pill">⚡ &lt; 300ms pipeline budget</span>
            <span class="qc-pill">🧬 5 quality metrics</span>
            <span class="qc-pill">🎚️ Live threshold tuning</span>
            <span class="qc-pill">v{APP_VERSION}</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- #
# Sidebar — live threshold tuning
# --------------------------------------------------------------------------- #

st.sidebar.markdown("### ⚙️ QC Threshold Settings")
st.sidebar.caption("Tune every gate live — no code changes required.")

st.sidebar.markdown("**Blur**")
blur_min = st.sidebar.slider(
    "Min Laplacian variance", 1.0, 100.0, float(DEFAULT_THRESHOLDS.blur_min), step=1.0
)

st.sidebar.markdown("**Brightness**")
brightness_min, brightness_max = st.sidebar.slider(
    "Acceptable range (grayscale mean)",
    0, 255,
    (int(DEFAULT_THRESHOLDS.brightness_min), int(DEFAULT_THRESHOLDS.brightness_max)),
)

st.sidebar.markdown("**Glare**")
glare_max = st.sidebar.slider(
    "Max glare fraction", 0.01, 0.30, float(DEFAULT_THRESHOLDS.glare_max_fraction), step=0.01
)

st.sidebar.markdown("**ROI Completeness**")
roi_min = st.sidebar.slider(
    "Min finger area fraction", 0.05, 0.60, float(DEFAULT_THRESHOLDS.roi_min_fraction), step=0.01
)

st.sidebar.markdown("**Ridge Clarity**")
ridge_min = st.sidebar.slider(
    "Min Gabor response score", 1.0, 60.0, float(DEFAULT_THRESHOLDS.ridge_min_score), step=1.0
)

st.sidebar.markdown("**Composite Pass Mark**")
pass_mark = st.sidebar.slider(
    "Min composite score to pass", 0.0, 100.0, float(DEFAULT_THRESHOLDS.composite_pass_score), step=1.0
)

st.sidebar.markdown("---")
with st.sidebar.expander("🧮 Composite score weights"):
    w_blur = st.slider("Weight: Blur", 0.0, 1.0, DEFAULT_WEIGHTS.blur, 0.05)
    w_bright = st.slider("Weight: Brightness", 0.0, 1.0, DEFAULT_WEIGHTS.brightness, 0.05)
    w_glare = st.slider("Weight: Glare", 0.0, 1.0, DEFAULT_WEIGHTS.glare, 0.05)
    w_roi = st.slider("Weight: ROI", 0.0, 1.0, DEFAULT_WEIGHTS.roi, 0.05)
    w_ridge = st.slider("Weight: Ridge", 0.0, 1.0, DEFAULT_WEIGHTS.ridge, 0.05)
    w_sum = w_blur + w_bright + w_glare + w_roi + w_ridge
    if abs(w_sum - 1.0) > 1e-6:
        st.caption(f"⚠️ Weights sum to {w_sum:.2f} (ideally 1.00) — scores are still computed as-is.")

thresholds = Thresholds(
    blur_min=blur_min,
    brightness_min=brightness_min,
    brightness_max=brightness_max,
    glare_max_fraction=glare_max,
    roi_min_fraction=roi_min,
    ridge_min_score=ridge_min,
    composite_pass_score=pass_mark,
)
weights = Weights(blur=w_blur, brightness=w_bright, glare=w_glare, roi=w_roi, ridge=w_ridge)
normalization = DEFAULT_NORMALIZATION


# --------------------------------------------------------------------------- #
# Main panel — upload + results
# --------------------------------------------------------------------------- #

left, right = st.columns([1, 1.15], gap="large")

with left:
    st.markdown("#### 📤 Upload a capture")
    uploaded_file = st.file_uploader(
        "Drag & drop a fingerprint image, or click to browse",
        type=["jpg", "jpeg", "png"],
        label_visibility="collapsed",
    )
    if uploaded_file is not None:
        st.image(uploaded_file, caption="Uploaded capture", use_container_width=True)
    else:
        st.markdown(
            """
            <div class="qc-card" style="text-align:center; padding:48px 20px;">
                <div style="font-size:2.6rem;">🖐️</div>
                <div style="color:var(--text-dim); margin-top:8px;">
                    No image yet — upload a fingertip capture to run the QC pipeline.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def badge(passed: bool) -> str:
    return (
        '<span class="badge badge-pass">✅ PASS</span>'
        if passed
        else '<span class="badge badge-fail">❌ FAIL</span>'
    )


def metric_card(title: str, value_str: str, sub: str, passed: bool, pct: float) -> str:
    bar_class = "progress-fill" if passed else "progress-fill fail"
    pct_clamped = max(0, min(100, pct))
    return f"""
    <div class="qc-card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <h3>{title}</h3>
            {badge(passed)}
        </div>
        <div class="metric-value">{value_str}</div>
        <div class="metric-sub">{sub}</div>
        <div class="progress-track">
            <div class="{bar_class}" data-target="{pct_clamped}" style="width:0%;"></div>
        </div>
    </div>
    """


with right:
    st.markdown("#### 📊 Quality Report")

    if uploaded_file is None:
        st.markdown(
            """
            <div class="qc-card" style="text-align:center; padding:48px 20px; color:var(--text-dim);">
                Results will appear here after you upload an image.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        image_bytes = uploaded_file.getvalue()
        with st.spinner("Running 5-metric quality gate..."):
            result = quality_gate(
                image_bytes,
                thresholds=thresholds,
                weights=weights,
                normalization=normalization,
            )

        score = result["composite_score"]
        passed = result["passed"]
        ring_deg = max(0.0, min(100.0, score)) / 100.0 * 360.0
        ring_color = "var(--accent-green)" if passed else "var(--accent-red)"

        # ---- Composite score ring + guidance banner (animated via JS) ---- #
        js_source = load_js_source()
        css_source = CSS_PATH.read_text(encoding="utf-8")

        guidance_class = "guidance-pass" if passed else "guidance-fail"
        guidance_icon = "✅" if passed else "⚠️"

        results_html = f"""
        <html>
        <head><style>{css_source}
            body {{ margin:0; background:transparent; font-family:'Segoe UI',sans-serif; }}
            .ring-wrap {{ display:flex; align-items:center; gap:26px; padding: 4px 4px 10px 4px;}}
            .score-ring {{
                width:150px; height:150px; border-radius:50%;
                background: conic-gradient({ring_color} {ring_deg}deg, rgba(255,255,255,0.06) 0deg);
                display:flex; align-items:center; justify-content:center;
                box-shadow: 0 0 30px rgba(34,211,238,0.10);
                animation: fadeSlideUp 0.6s ease both;
            }}
            .score-ring-inner {{
                width:118px; height:118px; border-radius:50%;
                background: #0d1526;
                display:flex; flex-direction:column; align-items:center; justify-content:center;
            }}
            #qc-score-value {{ font-size:2.1rem; font-weight:800; color:{ring_color}; }}
            .score-label {{ color:var(--text-dim); font-size:0.7rem; margin-top:2px; letter-spacing:0.5px;}}
            .verdict-title {{ font-size:1.3rem; font-weight:800; color:{ring_color}; margin-bottom:4px;}}
        </style></head>
        <body>
            <div class="ring-wrap">
                <div class="score-ring">
                    <div class="score-ring-inner">
                        <div id="qc-score-value">0.0</div>
                        <div class="score-label">/ 100</div>
                    </div>
                </div>
                <div>
                    <div class="verdict-title">{"CAPTURE ACCEPTED" if passed else "CAPTURE REJECTED"}</div>
                    <div style="color:var(--text-dim); font-size:0.85rem;">
                        Pipeline latency: {result['total_elapsed_ms']} ms
                    </div>
                </div>
            </div>
            <canvas id="qc-confetti-canvas" style="width:100%; height:0px;"></canvas>
            <div class="guidance-banner {guidance_class}" style="margin-top:6px;">
                <span style="font-size:1.3rem;">{guidance_icon}</span>
                <span>{result['guidance']}</span>
            </div>
            <script>{js_source}</script>
            <script>
                initResultsAnimation({{score: {score}, passed: {str(passed).lower()}}});
            </script>
        </body>
        </html>
        """
        components.html(results_html, height=260, scrolling=False)

        # ---- Five metric cards ---- #
        c1, c2 = st.columns(2)

        blur = result["blur"]
        bright = result["brightness"]
        glare = result["glare"]
        roi = result["roi"]
        ridge = result["ridge"]

        with c1:
            st.markdown(
                metric_card(
                    "🔎 Blur (Laplacian Variance)",
                    f"{blur['blur_score']}",
                    f"Reject if below {thresholds.blur_min:.1f}",
                    not blur["is_blurry"],
                    min(100, blur["blur_score"] / max(1.0, thresholds.blur_min * 3) * 100),
                ),
                unsafe_allow_html=True,
            )
            bright_ok = not (bright["too_dark"] or bright["too_bright"])
            st.markdown(
                metric_card(
                    "💡 Brightness (Mean Intensity)",
                    f"{bright['brightness']}",
                    f"Acceptable range {thresholds.brightness_min:.0f}–{thresholds.brightness_max:.0f}",
                    bright_ok,
                    (bright["brightness"] / 255.0) * 100,
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                metric_card(
                    "✨ Glare (Over-saturation Ratio)",
                    f"{glare['glare_fraction']*100:.2f}%",
                    f"Reject if above {thresholds.glare_max_fraction*100:.1f}%",
                    not glare["has_glare"],
                    100 - min(100, (glare["glare_fraction"] / max(0.001, thresholds.glare_max_fraction)) * 100),
                ),
                unsafe_allow_html=True,
            )

        with c2:
            st.markdown(
                metric_card(
                    "🖼️ ROI Completeness (Finger Area)",
                    f"{roi['roi_fraction']*100:.1f}%",
                    f"Reject if below {thresholds.roi_min_fraction*100:.0f}%",
                    roi["roi_complete"],
                    min(100, (roi["roi_fraction"] / max(0.01, thresholds.roi_min_fraction * 2)) * 100),
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                metric_card(
                    "🧬 Ridge Clarity (Gabor Response)",
                    f"{ridge['ridge_score']}",
                    f"Reject if below {thresholds.ridge_min_score:.1f}",
                    ridge["ridges_clear"],
                    min(100, (ridge["ridge_score"] / max(1.0, thresholds.ridge_min_score * 2)) * 100),
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                metric_card(
                    "🎯 Composite Score",
                    f"{score} / 100",
                    f"Pass mark: {thresholds.composite_pass_score:.0f}",
                    passed,
                    score,
                ),
                unsafe_allow_html=True,
            )

        with st.expander("🔬 Raw JSON output (for debugging / API integration)"):
            st.json(result)


st.markdown(
    """
    <div class="qc-footer">
        Fingerprint Quality Control System · Built for contactless biometric capture pipelines ·
        Runs 100% locally, no external services or paid APIs.
    </div>
    """,
    unsafe_allow_html=True,
)
