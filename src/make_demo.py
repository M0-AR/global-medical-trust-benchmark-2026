"""Generate assets/demo.mp4 + assets/demo.gif from live_results.csv (no hand-made media)."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "live_results.csv"
MP4 = ROOT / "assets" / "demo.mp4"
GIF = ROOT / "assets" / "demo.gif"

rows = list(csv.DictReader(CSV.open(encoding="utf-8")))
rows = sorted(rows, key=lambda r: float(r["trust_100"]), reverse=True)
names = [r["name"].replace(" / MEDLINE", "") for r in rows]
scores = [float(r["trust_100"]) for r in rows]
colors = ["#34d399" if float(r["http_status"]) == 200 else "#fbbf24" for r in rows]

fig, ax = plt.subplots(figsize=(8, 4.6))
fig.patch.set_facecolor("#0b1020")
ax.set_facecolor("#0b1020")

def frame(f):
    ax.clear()
    ax.set_facecolor("#0b1020")
    k = max(1, int(len(names) * (f + 1) / 40))
    ax.barh(names[:k][::-1], scores[:k][::-1], color=colors[:k][::-1])
    ax.set_xlim(0, 105)
    ax.set_title(f"Global Medical Trust 2026 — live trust/100 (frame {f+1}/40)", color="white", fontsize=11)
    ax.tick_params(colors="white", labelsize=8)
    for i, (n, s) in enumerate(zip(names[:k], scores[:k])):
        ax.text(s + 1, len(names[:k]) - 1 - (len(names[:k]) - k + i) * 0 if False else None, "", color="white")
    # annotate values
    for y, s in enumerate(scores[:k][::-1]):
        ax.text(s + 1, y, f"{s:.1f}", color="white", fontsize=8, va="center")
    fig.tight_layout()

anim = FuncAnimation(fig, frame, frames=40, interval=120)
anim.save(MP4, writer="ffmpeg", fps=12, dpi=110)
print("wrote", MP4, MP4.stat().st_size, "bytes")
# lightweight GIF: every 4th frame, smaller
anim2 = FuncAnimation(fig, frame, frames=12, interval=300)
anim2.save(GIF, writer="pillow", fps=4, dpi=70)
print("wrote", GIF, GIF.stat().st_size, "bytes")
