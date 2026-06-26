"""
Generate benchmark charts from benchmark_models.py JSON output.

Single-model mode (gpt-oss-120b per-run charts):
    python3 gen_benchmark_charts.py

All-models comparison mode:
    python3 gen_benchmark_charts.py --json docs/benchmark_all_models.json --output docs/
"""
import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ── Style ─────────────────────────────────────────────────────────────────────
NVIDIA_GREEN = "#76b900"
BLUE         = "#4c9be8"
AMBER        = "#f0a500"
RED          = "#e05252"
PURPLE       = "#9b59b6"
TEAL         = "#1abc9c"
GREY         = "#aaaaaa"
DARK_GREY    = "#666666"
BG           = "#ffffff"
PANEL_BG     = "#f8f8f8"
TEXT         = "#222222"
GRID         = "#e0e0e0"

MODEL_COLORS = [
    NVIDIA_GREEN, BLUE, AMBER, PURPLE, TEAL, RED,
    "#e67e22", "#2ecc71", "#3498db", "#e74c3c",
    "#9b59b6", "#1abc9c", "#f39c12", "#d35400",
]

plt.rcParams.update({
    "font.family":       "DejaVu Sans",
    "font.size":         11,
    "axes.facecolor":    PANEL_BG,
    "figure.facecolor":  BG,
    "axes.edgecolor":    GRID,
    "axes.labelcolor":   TEXT,
    "xtick.color":       TEXT,
    "ytick.color":       TEXT,
    "text.color":        TEXT,
    "axes.titlesize":    13,
    "axes.titleweight":  "bold",
    "axes.titlepad":     12,
    "axes.grid":         True,
    "grid.color":        GRID,
    "grid.linewidth":    0.8,
    "axes.spines.top":   False,
    "axes.spines.right": False,
})

CAPTION = dict(ha="center", fontsize=9, color=DARK_GREY)


# ── Helpers ───────────────────────────────────────────────────────────────────

def shorten(name: str) -> str:
    replacements = {
        "Nemotron-Nano-Omni-30B": "Nemotron-Omni-30B",
    }
    return replacements.get(name, name)


def save(fig, path: Path, caption: str = ""):
    if caption:
        fig.text(0.5, -0.01, caption, **CAPTION)
    plt.tight_layout()
    fig.savefig(path, format="png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"  ✓ {path.name}")


# ═══════════════════════════════════════════════════════════════════════════════
# Single-model per-run charts  (hardcoded gpt-oss-120b latest run)
# ═══════════════════════════════════════════════════════════════════════════════

def gen_single_model_charts(out_dir: Path):
    """Per-run charts for the latest gpt-oss-120b benchmark (2026-06-25)."""
    TG_RUNS      = [56.8, 56.7, 56.8]
    TTFT_MS      = 83
    PP_RUNS      = [1577.4, 37.3, 52.6]
    PP_COLD      = [37.3, 52.6]
    TG_MEAN      = sum(TG_RUNS) / len(TG_RUNS)
    PP_COLD_MEAN = sum(PP_COLD) / len(PP_COLD)
    CACHE_HIT    = 99.9

    # TG per run
    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(3)
    bars = ax.bar(x, TG_RUNS, color=NVIDIA_GREEN, width=0.5, zorder=3,
                  edgecolor="white", linewidth=0.5)
    ax.set_xticks(x); ax.set_xticklabels(["Run 1", "Run 2", "Run 3"])
    ax.set_ylabel("Tokens / second"); ax.set_title("Generation Speed — gpt-oss-120b")
    ax.set_ylim(50, 62)
    for b, v in zip(bars, TG_RUNS):
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.2,
                f"{v:.1f}", ha="center", va="bottom", fontsize=10,
                fontweight="bold", color=TEXT)
    ax.axhline(TG_MEAN, color=BLUE, linewidth=1.5, linestyle="--", zorder=4,
               label=f"Mean: {TG_MEAN:.1f} t/s")
    ax.legend(framealpha=0.9, fontsize=10)
    save(fig, out_dir / "benchmark_tg_speed.png",
         "3 iterations · temperature=0 · short prompt (~83 tokens) · 200 generated tokens")

    # PP per run (log scale)
    fig, ax = plt.subplots(figsize=(7, 4))
    pp_colors = [AMBER, NVIDIA_GREEN, NVIDIA_GREEN]
    bars = ax.bar(np.arange(3), PP_RUNS, color=pp_colors, width=0.5, zorder=3,
                  edgecolor="white", linewidth=0.5)
    ax.set_yscale("log")
    ax.set_xticks(np.arange(3))
    ax.set_xticklabels(["Run 1\n(cache warm)", "Run 2\n(cold)", "Run 3\n(cold)"])
    ax.set_ylabel("Tokens / second (log scale)")
    ax.set_title("Prompt Processing Speed — gpt-oss-120b")
    for b, v in zip(bars, PP_RUNS):
        ax.text(b.get_x() + b.get_width()/2, b.get_height() * 1.15,
                f"{v:.1f}", ha="center", va="bottom", fontsize=10,
                fontweight="bold", color=TEXT)
    ax.axhline(PP_COLD_MEAN, color=BLUE, linewidth=1.5, linestyle="--", zorder=4,
               label=f"Cold mean (runs 2–3): {PP_COLD_MEAN:.1f} t/s")
    ax.legend(framealpha=0.9, fontsize=10)
    ax.annotate("Cache-warm artifact\n(excluded from mean)",
                xy=(0, PP_RUNS[0]), xytext=(0.6, 800),
                arrowprops=dict(arrowstyle="->", color=AMBER, lw=1.5),
                fontsize=9, color=AMBER)
    save(fig, out_dir / "benchmark_pp_speed.png",
         "3 iterations · ~1 126 token prompt · Run 1 hit warm cache from prior session")

    # Key metrics summary
    fig, ax = plt.subplots(figsize=(8, 4.5))
    metrics = [
        ("Generation speed",  TG_MEAN,        60.0,  NVIDIA_GREEN),
        ("Prompt processing", PP_COLD_MEAN,   200.0,  BLUE),
        ("TTFT",              1000 - TTFT_MS, 950.0,  BLUE),
        ("Cache hit rate",    CACHE_HIT,      100.0,  NVIDIA_GREEN),
    ]
    raw_labels = [f"{TG_MEAN:.1f} t/s", f"{PP_COLD_MEAN:.0f} t/s (cold)",
                  f"{TTFT_MS} ms", f"{CACHE_HIT:.1f}%"]
    labels = [m[0] for m in metrics]
    pcts   = [min(m[1] / m[2] * 100, 100) for m in metrics]
    colors = [m[3] for m in metrics]
    y = np.arange(len(labels))
    hbars = ax.barh(y, pcts, color=colors, height=0.5, zorder=3,
                    edgecolor="white", linewidth=0.5)
    ax.set_xlim(0, 115); ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=11)
    ax.set_xlabel("% of reference maximum")
    ax.set_title("Key Metrics Summary — gpt-oss-120b")
    ax.axvline(100, color=GREY, linewidth=1, linestyle=":", zorder=2)
    for hb, pct, lbl in zip(hbars, pcts, raw_labels):
        ax.text(pct + 1, hb.get_y() + hb.get_height()/2,
                lbl, va="center", fontsize=10, fontweight="bold", color=TEXT)
    save(fig, out_dir / "benchmark_summary.png",
         "Reference maxima: TG 60 t/s · PP 200 t/s · TTFT <50 ms → 950 ms range · Cache 100%")


# ═══════════════════════════════════════════════════════════════════════════════
# Multi-model comparison charts  (from JSON results)
# ═══════════════════════════════════════════════════════════════════════════════

def gen_comparison_charts(results: list, out_dir: Path):
    ok = [r for r in results if r.get("warmup_ok") and r.get("gen")]
    if not ok:
        print("  No successful results to chart.")
        return

    ok_sorted = sorted(ok, key=lambda r: r["gen"].get("tg_tps_mean", 0), reverse=True)
    labels  = [shorten(r["model"]) for r in ok_sorted]
    tg_vals = [r["gen"].get("tg_tps_mean", 0) for r in ok_sorted]
    tg_err  = [r["gen"].get("tg_tps_std",  0) for r in ok_sorted]
    ttft    = [r["gen"].get("ttft_ms_mean", 0) for r in ok_sorted]
    pp_vals = [r["pp"].get("pp_tps_mean",  0) for r in ok_sorted]
    pp_err  = [r["pp"].get("pp_tps_std",   0) for r in ok_sorted]
    cache   = [r.get("cache", {}).get("hit_rate_pct", 0) for r in ok_sorted]
    colors  = [MODEL_COLORS[i % len(MODEL_COLORS)] for i in range(len(ok_sorted))]
    n       = len(ok_sorted)
    y       = np.arange(n)
    h       = max(4, n * 0.65 + 1.5)

    def hbar(vals, errs, title, xlabel, fname, ref=None):
        fig, ax = plt.subplots(figsize=(10, h))
        has_err = any(e > 0 for e in errs)
        ax.barh(y, vals,
                xerr=errs if has_err else None,
                color=colors, height=0.6, zorder=3,
                edgecolor="white", linewidth=0.5,
                error_kw=dict(ecolor=DARK_GREY, capsize=4, linewidth=1.2))
        ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=11)
        ax.set_xlabel(xlabel); ax.set_title(title)
        if ref is not None:
            ax.axvline(ref, color=GREY, linewidth=1, linestyle=":", zorder=2)
        mx = max(vals) if vals else 1
        for i, (v, bar) in enumerate(zip(vals, ax.patches)):
            if v > 0:
                ax.text(v + mx * 0.01, bar.get_y() + bar.get_height()/2,
                        f"{v:.1f}", va="center", fontsize=9,
                        fontweight="bold", color=TEXT)
        save(fig, out_dir / fname,
             "Sorted by generation speed (fastest first) · 3 iterations · temperature=0")

    hbar(tg_vals, tg_err,
         "Generation Speed — All Models", "Tokens / second (TG t/s)",
         "comparison_tg_speed.png")

    hbar(ttft, [0]*n,
         "Time to First Token — All Models", "Milliseconds (lower is better)",
         "comparison_ttft.png", ref=100)

    hbar(pp_vals, pp_err,
         "Prompt Processing Speed — All Models", "Tokens / second (PP t/s)",
         "comparison_pp_speed.png")

    hbar(cache, [0]*n,
         "KV Cache Hit Rate — All Models", "% tokens served from cache (second request)",
         "comparison_cache.png", ref=100)

    # Combined overview: TG speed + TTFT side by side
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, h))
    fig.suptitle("Performance Overview — All Models", fontsize=14,
                 fontweight="bold", y=1.01)

    ax1.barh(y, tg_vals, color=colors, height=0.6, zorder=3,
             edgecolor="white", linewidth=0.5)
    ax1.set_yticks(y); ax1.set_yticklabels(labels, fontsize=10)
    ax1.set_xlabel("Generation speed (t/s)"); ax1.set_title("Token Generation Speed")
    mx1 = max(tg_vals) if tg_vals else 1
    for v, bar in zip(tg_vals, ax1.patches):
        if v > 0:
            ax1.text(v + mx1*0.01, bar.get_y() + bar.get_height()/2,
                     f"{v:.1f}", va="center", fontsize=9, fontweight="bold", color=TEXT)

    ax2.barh(y, ttft, color=colors, height=0.6, zorder=3,
             edgecolor="white", linewidth=0.5)
    ax2.set_yticks(y); ax2.set_yticklabels([], fontsize=10)
    ax2.set_xlabel("Time to first token (ms, lower = better)")
    ax2.set_title("Time to First Token")
    ax2.axvline(100, color=GREY, linewidth=1, linestyle=":", zorder=2, label="100 ms")
    ax2.legend(fontsize=9, framealpha=0.9)
    mx2 = max(ttft) if ttft else 1
    for v, bar in zip(ttft, ax2.patches):
        if v > 0:
            ax2.text(v + mx2*0.01, bar.get_y() + bar.get_height()/2,
                     f"{v:.0f} ms", va="center", fontsize=9, fontweight="bold", color=TEXT)

    save(fig, out_dir / "comparison_overview.png",
         "Sorted by generation speed (fastest first) · 3 iterations · temperature=0")

    # Speed vs TTFT scatter
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_title("Speed vs Time-to-First-Token — All Models", pad=14)
    for i, r in enumerate(ok_sorted):
        tg = r["gen"].get("tg_tps_mean", 0)
        tt = r["gen"].get("ttft_ms_mean", 0)
        ax.scatter(tg, tt, color=colors[i], s=200, zorder=4,
                   edgecolors="white", linewidth=1.5)
        ax.annotate(shorten(r["model"]), (tg, tt),
                    textcoords="offset points", xytext=(8, 4),
                    fontsize=9, color=TEXT)
    ax.set_xlabel("Generation speed (t/s)  →  faster")
    ax.set_ylabel("Time to first token (ms)  ↓  lower is better")
    ax.axhline(100, color=GREY, linewidth=1, linestyle=":", label="100 ms TTFT")
    ax.legend(fontsize=9, framealpha=0.9)
    save(fig, out_dir / "comparison_scatter.png",
         "Best quadrant: high t/s AND low TTFT (bottom-right)")

    print(f"\n  Generated {n}-model comparison charts.")


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Generate benchmark PNG charts")
    parser.add_argument("--json", metavar="FILE",
                        help="JSON results from benchmark_models.py --json (enables comparison charts)")
    parser.add_argument("--output", metavar="DIR",
                        default="/home/sysadmin/codebase/bin/docs",
                        help="Output directory (default: docs/)")
    parser.add_argument("--single", action="store_true",
                        help="Also regenerate single-model gpt-oss-120b charts")
    args = parser.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.json:
        print(f"Loading {args.json} ...")
        with open(args.json) as f:
            results = json.load(f)
        print(f"  {len(results)} model result(s) loaded")
        print("\nGenerating comparison charts ...")
        gen_comparison_charts(results, out_dir)
        if args.single or len(results) == 1:
            print("\nGenerating single-model per-run charts ...")
            gen_single_model_charts(out_dir)
    else:
        print("No --json provided; generating single-model gpt-oss-120b charts only.")
        gen_single_model_charts(out_dir)

    print(f"\nAll charts written to {out_dir}/")


if __name__ == "__main__":
    main()
