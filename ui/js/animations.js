/* =========================================================================
   Fingerprint Quality Control System — UI Animations
   Vanilla JS only. Runs inside a sandboxed Streamlit components.html iframe.
   ========================================================================= */

/**
 * Animate a numeric counter from 0 up to `endValue` inside the element
 * with id `elementId`. Used for the big composite-score readout.
 */
function animateCountUp(elementId, endValue, duration = 1200, suffix = "") {
  const el = document.getElementById(elementId);
  if (!el) return;

  const startTime = performance.now();
  const startValue = 0;

  function step(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    // easeOutCubic for a natural "settling" feel
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = startValue + (endValue - startValue) * eased;
    el.textContent = current.toFixed(1) + suffix;

    if (progress < 1) {
      requestAnimationFrame(step);
    } else {
      el.textContent = endValue.toFixed(1) + suffix;
    }
  }
  requestAnimationFrame(step);
}

/**
 * Animate every `.progress-fill` bar from width 0 to its
 * `data-target` percentage (staggered for a cascading effect).
 */
function animateBars() {
  const bars = document.querySelectorAll(".progress-fill");
  bars.forEach((bar, i) => {
    const target = bar.getAttribute("data-target") || "0";
    setTimeout(() => {
      bar.style.width = target + "%";
    }, i * 120);
  });
}

/**
 * Fire a lightweight canvas confetti burst — used only when a capture
 * PASSES the quality gate, as positive reinforcement for the user.
 */
function launchConfetti(canvasId) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const W = (canvas.width = canvas.offsetWidth);
  const H = (canvas.height = 160);

  const colors = ["#22d3ee", "#3b82f6", "#8b5cf6", "#34d399", "#fbbf24"];
  const particles = Array.from({ length: 60 }, () => ({
    x: Math.random() * W,
    y: -10 - Math.random() * 40,
    r: 3 + Math.random() * 3,
    vx: -1.5 + Math.random() * 3,
    vy: 2 + Math.random() * 2.5,
    color: colors[Math.floor(Math.random() * colors.length)],
    rot: Math.random() * Math.PI,
    vrot: -0.15 + Math.random() * 0.3,
  }));

  let frame = 0;
  const maxFrames = 110;

  function tick() {
    ctx.clearRect(0, 0, W, H);
    particles.forEach((p) => {
      p.x += p.vx;
      p.y += p.vy;
      p.rot += p.vrot;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.fillStyle = p.color;
      ctx.fillRect(-p.r, -p.r / 2, p.r * 2, p.r);
      ctx.restore();
    });
    frame++;
    if (frame < maxFrames) {
      requestAnimationFrame(tick);
    } else {
      ctx.clearRect(0, 0, W, H);
    }
  }
  requestAnimationFrame(tick);
}

/**
 * Entry point called once the results DOM is ready. Kicks off the
 * counter, the progress bars, and (conditionally) the confetti burst.
 */
function initResultsAnimation(config) {
  animateCountUp("qc-score-value", config.score, 1200, "");
  animateBars();
  if (config.passed) {
    launchConfetti("qc-confetti-canvas");
  }
}
