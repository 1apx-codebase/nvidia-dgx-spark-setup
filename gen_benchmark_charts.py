"""Generate benchmark charts for gpt-oss-120b results."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

DOCS_DIR = "/home/sysadmin/codebase/bin/docs"

# ── Data ─────────────────────────────────────────────────────────────────────
TG_RUNS   = [56.8, 56.7, 56.8]
TTFT_RUNS = [80, 84, 85]          # approximated from mean=83, std=3
PP_RUNS   = [1577.4, 37.3, 52.6]
PP_COLD   = [37.3, 52.6]          # true cold (excluding cache-warm run 1)

TG_MEAN   = np.mean(TG_RUNS)
TTFT_MEAN = 83
PP_COLD_MEAN = np.mean(PP_COLD)
CACHE_HIT = 99.9

# ── Style ─────────────────────────────────────────────────────────────────────
NVIDIA_GREEN = "#76b900"
BLUE         = "#4c9be8"
AMBER        = "#f0a500"
RED          = "#e05252"
GREY         = "#aaaaaa"
BG           = "#ffffff"
PANEL_BG     = "#f8f8f8"
TEXT         = "#222222"
GRID         = "#e0e0e0"

plt.rcParams.update({
    "font.family":      "DejaVu Sans",
    "font.size":        11,
    "axes.facecolor":   PANEL_BG,
    "figure.facecolor": BG,
    "axes.edgecolor":   GRID,
    "axes.labelcolor":  TEXT,
    "xtick.color":      TEXT,
    "ytick.color":      TEXT,
    "text.color":       TEXT,
    "axes.titlesize":   12,
    "axes.titleweight": "bold",
    "axes.titlepad":    10,
    "axes.grid":        True,
    "grid.color":       GRID,
    "grid.linewidth":   0.8,
    "axes.spines.top":  False,
    "axes.spines.right":False,
})

def bar(ax, labels, values, colors, ylabel, title, ylim=None, fmt=".1f"):
    x = np.arange(len(labels))
    bars = ax.bar(x, values, color=colors, width=0.5, zorder=3, edgecolor="white", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if ylim:
        ax.set_ylim(*ylim)
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + ylim[1]*0.02 if ylim else b.get_height()*1.02,
                f"{v:{fmt}}", ha="center", va="bottom", fontsize=10, fontweight="bold", color=TEXT)
    return bars

# ═══════════════════════════════════════════════════════════════════════════════
# Chart 1 — Generation speed per run
# ═══════════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(7, 4))
fig.patch.set_facecolor(BG)

colors = [NVIDIA_GREEN] * 3
bar(ax, ["Run 1", "Run 2", "Run 3"], TG_RUNS, colors,
    "Tokens / second", "Generation Speed — gpt-oss-120b", ylim=(50, 62), fmt=".1f")

ax.axhline(TG_MEAN, color=BLUE, linewidth=1.5, linestyle="--", zorder=4, label=f"Mean: {TG_MEAN:.1f} t/s")
ax.legend(framealpha=0.9, fontsize=10)
ax.set_ylim(50, 62)

fig.text(0.5, -0.02,
         "3 iterations · temperature=0 · short prompt (~83 tokens) · 200 generated tokens",
         ha="center", fontsize=9, color=GREY)

plt.tight_layout()
fig.savefig(f"{DOCS_DIR}/benchmark_tg_speed.png", format="png", bbox_inches="tight", dpi=150)
plt.close(fig)
print("✓ benchmark_tg_speed.png")

# ═══════════════════════════════════════════════════════════════════════════════
# Chart 2 — Prompt processing per run (log scale, outlier annotated)
# ═══════════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(7, 4))
fig.patch.set_facecolor(BG)

pp_colors = [AMBER, NVIDIA_GREEN, NVIDIA_GREEN]
x = np.arange(3)
bars = ax.bar(x, PP_RUNS, color=pp_colors, width=0.5, zorder=3, edgecolor="white", linewidth=0.5)
ax.set_yscale("log")
ax.set_xticks(x)
ax.set_xticklabels(["Run 1\n(cache warm)", "Run 2\n(cold)", "Run 3\n(cold)"])
ax.set_ylabel("Tokens / second (log scale)")
ax.set_title("Prompt Processing Speed — gpt-oss-120b")

for b, v in zip(bars, PP_RUNS):
    ax.text(b.get_x() + b.get_width() / 2, b.get_height() * 1.15,
            f"{v:.1f}", ha="center", va="bottom", fontsize=10, fontweight="bold", color=TEXT)

ax.axhline(PP_COLD_MEAN, color=BLUE, linewidth=1.5, linestyle="--", zorder=4,
           label=f"Cold mean (runs 2–3): {PP_COLD_MEAN:.1f} t/s")
ax.legend(framealpha=0.9, fontsize=10)

# Annotate the outlier
ax.annotate("Cache-warm artifact\n(excludes from mean)",
            xy=(0, PP_RUNS[0]), xytext=(0.6, 800),
            arrowprops=dict(arrowstyle="->", color=AMBER, lw=1.5),
            fontsize=9, color=AMBER)

fig.text(0.5, -0.02,
         "3 iterations · ~1 126 token prompt · Run 1 hit warm cache from prior session",
         ha="center", fontsize=9, color=GREY)

plt.tight_layout()
fig.savefig(f"{DOCS_DIR}/benchmark_pp_speed.png", format="png", bbox_inches="tight", dpi=150)
plt.close(fig)
print("✓ benchmark_pp_speed.png")

# ═══════════════════════════════════════════════════════════════════════════════
# Chart 3 — Key metrics summary (horizontal bars vs reference points)
# ═══════════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(8, 4.5))
fig.patch.set_facecolor(BG)

# Normalise each metric to % of "excellent" reference
metrics = [
    ("Generation speed",   TG_MEAN,        60.0,  "t/s",   NVIDIA_GREEN),
    ("Prompt processing",  PP_COLD_MEAN,   200.0,  "t/s",   BLUE),
    ("TTFT",               1000 - TTFT_MEAN, 1000-50, "ms inverse", BLUE),
    ("Cache hit rate",     CACHE_HIT,      100.0,  "%",     NVIDIA_GREEN),
]

labels   = [m[0] for m in metrics]
pcts     = [min(m[1] / m[2] * 100, 100) for m in metrics]
raw_vals = [m[1] for m in metrics]
units    = [m[3] for m in metrics]
colors   = [m[4] for m in metrics]

y = np.arange(len(labels))
hbars = ax.barh(y, pcts, color=colors, height=0.5, zorder=3, edgecolor="white", linewidth=0.5)
ax.set_xlim(0, 115)
ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=11)
ax.set_xlabel("% of reference maximum")
ax.set_title("Key Metrics Summary — gpt-oss-120b")
ax.axvline(100, color=GREY, linewidth=1, linestyle=":", zorder=2)

# Annotate with raw values
raw_labels = [
    f"{TG_MEAN:.1f} t/s",
    f"{PP_COLD_MEAN:.0f} t/s (cold)",
    f"{TTFT_MEAN} ms",
    f"{CACHE_HIT:.1f}%",
]
for hb, pct, label in zip(hbars, pcts, raw_labels):
    ax.text(pct + 1, hb.get_y() + hb.get_height() / 2,
            label, va="center", fontsize=10, fontweight="bold", color=TEXT)

fig.text(0.5, -0.02,
         "Reference maxima: TG 60 t/s · PP 200 t/s · TTFT <50 ms → 1000 ms range · Cache 100%",
         ha="center", fontsize=9, color=GREY)

plt.tight_layout()
fig.savefig(f"{DOCS_DIR}/benchmark_summary.png", format="png", bbox_inches="tight", dpi=150)
plt.close(fig)
print("✓ benchmark_summary.png")

print("\nAll charts written to", DOCS_DIR)
