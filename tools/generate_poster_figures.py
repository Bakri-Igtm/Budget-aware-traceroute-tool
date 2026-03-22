"""
Generate poster-ready figures from compare_traces results.
Usage: python -m tools.generate_poster_figures
"""

import json
import glob
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ── Load the most recent results file ──────────────────────────────────
files = sorted(glob.glob("compare_results_*.json"))
if not files:
    raise FileNotFoundError("No compare_results_*.json found in cwd")
with open(files[-1]) as f:
    data = json.load(f)

results = data["results"]
targets    = [r["target"] for r in results]
accuracies = [r["accuracy"] for r in results]
reg_probes = [r["reg_probes"] for r in results]
bud_probes = [r["bud_probes"] for r in results]
savings    = [r - b for r, b in zip(reg_probes, bud_probes)]
savings_pct = [(r - b) / r * 100 if r else 0 for r, b in zip(reg_probes, bud_probes)]

# Poster-friendly style
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 13,
    "axes.titlesize": 16,
    "axes.labelsize": 14,
    "figure.dpi": 300,
})

# ═══════════════════════════════════════════════════════════════════════
# FIGURE 1 — Scatter: Regular vs Budget probes with y = x reference
# ═══════════════════════════════════════════════════════════════════════
fig1, ax1 = plt.subplots(figsize=(7, 6))

colors = ['#2ecc71' if a == 100 else '#e67e22' if a >= 90 else '#e74c3c'
          for a in accuracies]

ax1.scatter(reg_probes, bud_probes, c=colors, edgecolors='white',
            linewidths=0.5, s=70, zorder=3, alpha=0.9)

# y = x line (no savings)
lim = max(max(reg_probes), max(bud_probes)) + 5
ax1.plot([0, lim], [0, lim], ls='--', color='gray', lw=1, label='No savings (y = x)')

# Fill the savings region
ax1.fill_between([0, lim], [0, lim], [0, 0], alpha=0.07, color='green')
ax1.text(lim * 0.65, lim * 0.25, 'Savings\nregion', fontsize=12,
         color='green', fontstyle='italic', ha='center', alpha=0.6)

ax1.set_xlabel('Standard Traceroute Probes')
ax1.set_ylabel('Budget Trace Probes')
ax1.set_title('Probe Count: Standard vs. Budget Trace')
ax1.set_xlim(0, lim)
ax1.set_ylim(0, lim)
ax1.set_aspect('equal')
ax1.legend(loc='upper left', fontsize=11)

# Custom legend for accuracy colors
from matplotlib.lines import Line2D
legend_els = [
    Line2D([0], [0], marker='o', color='w', markerfacecolor='#2ecc71',
           markersize=9, label='100 % accuracy'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor='#e67e22',
           markersize=9, label='90–99 % accuracy'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor='#e74c3c',
           markersize=9, label='< 90 % accuracy'),
    Line2D([0], [0], ls='--', color='gray', label='No savings (y = x)'),
]
ax1.legend(handles=legend_els, loc='upper left', fontsize=10,
           framealpha=0.9)

ax1.grid(True, alpha=0.3)
fig1.tight_layout()
fig1.savefig("poster_fig1_scatter.png", dpi=300, bbox_inches='tight')
print("Saved: poster_fig1_scatter.png")

# ═══════════════════════════════════════════════════════════════════════
# FIGURE 2 — Summary dashboard: accuracy histogram + key metrics
# ═══════════════════════════════════════════════════════════════════════
fig2, axes = plt.subplots(1, 2, figsize=(12, 5),
                           gridspec_kw={'width_ratios': [1.3, 1]})

# --- Left panel: Accuracy distribution ---
ax2a = axes[0]
bins = [70, 75, 80, 85, 90, 95, 100.01]  # 100.01 so 100% falls inside last bin
counts, edges, patches = ax2a.hist(accuracies, bins=bins, edgecolor='white',
                                    linewidth=1.2, color='#3498db', rwidth=0.88)
# Color the 100% bin green
for patch, left_edge in zip(patches, edges[:-1]):
    if left_edge >= 95:
        patch.set_facecolor('#2ecc71')

ax2a.set_xlabel('Path Accuracy (%)')
ax2a.set_ylabel('Number of Targets')
ax2a.set_title('Accuracy Distribution (n = 85)')
ax2a.xaxis.set_major_locator(mticker.FixedLocator([70, 75, 80, 85, 90, 95, 100]))
ax2a.set_xlim(68, 102)

# Annotate the 100% bar
perfect = sum(1 for a in accuracies if a == 100)
bar_100 = patches[-1]
ax2a.annotate(f'{perfect} targets\n({perfect/len(accuracies)*100:.0f}%)',
              xy=(bar_100.get_x() + bar_100.get_width() / 2, bar_100.get_height()),
              xytext=(0, 10), textcoords='offset points', ha='center',
              fontsize=11, fontweight='bold', color='#27ae60')

ax2a.grid(axis='y', alpha=0.3)

# --- Right panel: key metric cards ---
ax2b = axes[1]
ax2b.axis('off')

avg_acc = np.mean(accuracies)
total_reg = sum(reg_probes)
total_bud = sum(bud_probes)
reduction = (total_reg - total_bud) / total_reg * 100

metrics = [
    ("Targets Tested",      f"{len(results)}"),
    ("Mean Accuracy",       f"{avg_acc:.1f} %"),
    ("100 % Accurate",      f"{perfect} / {len(results)}  ({perfect/len(results)*100:.0f} %)"),
    ("Total Probes Saved",  f"{total_reg - total_bud}"),
    ("Probe Reduction",     f"{reduction:.1f} %"),
]

y_start = 0.92
for i, (label, value) in enumerate(metrics):
    y = y_start - i * 0.18
    ax2b.text(0.05, y, label, transform=ax2b.transAxes,
              fontsize=13, color='#555', va='top')
    ax2b.text(0.95, y, value, transform=ax2b.transAxes,
              fontsize=15, fontweight='bold', color='#2c3e50', va='top', ha='right')
    if i < len(metrics) - 1:
        ax2b.plot([0.05, 0.95], [y - 0.07, y - 0.07],
                  color='#ddd', lw=0.8, transform=ax2b.transAxes, clip_on=False)

ax2b.set_title('Key Metrics', pad=12)

fig2.tight_layout(w_pad=3)
fig2.savefig("poster_fig2_dashboard.png", dpi=300, bbox_inches='tight')
print("Saved: poster_fig2_dashboard.png")

plt.show()
print("\nDone — two figures saved to working directory.")
