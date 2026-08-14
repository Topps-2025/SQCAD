"""Render the spacious SQCAD core-mechanism figure.

The figure follows the original core-mechanism composition: three motivating
memory cases, one central qualification-to-access pipeline, three access
outcomes, and one invariant strip.  Retrieval algorithms and engineering
components are intentionally omitted because they are not SQCAD's mechanism.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon
from pathlib import Path


INK = "#17324A"
MUTED = "#5C7285"
LINE = "#758696"
BLUE = "#3E78B7"
BLUE_BG = "#EAF3FF"
TEAL = "#2D8588"
TEAL_BG = "#E9F7F6"
AMBER = "#B96B00"
AMBER_BG = "#FFF2DB"
PURPLE = "#7A4BA7"
PURPLE_BG = "#F3EAFF"
GREEN = "#37895D"
GREEN_BG = "#EAF7EF"
RED = "#B84E50"
RED_BG = "#FFF0F0"
GRAY = "#748493"
GRAY_BG = "#F1F4F6"
PAGE = "#FBFCFE"


def box(ax, x, y, w, h, title, body, edge, fill, *, center=False,
        title_size=9.2, body_size=7.8, lw=1.55):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.20",
        facecolor=fill, edgecolor=edge, linewidth=lw))
    ha = "center" if center else "left"
    tx = x + w / 2 if center else x + 0.62
    ax.text(tx, y + h - 0.72, title, fontsize=title_size,
            fontweight="bold", color=INK, ha=ha, va="top",
            family="DejaVu Sans")
    ax.plot([x + 0.55, x + w - 0.55], [y + h - 1.48, y + h - 1.48],
            color=edge, linewidth=0.72)
    ax.text(tx, y + h - 2.02, body, fontsize=body_size, color=MUTED,
            ha=ha, va="top", linespacing=1.68, family="DejaVu Sans")


def arrow(ax, start, end, color=LINE, *, lw=1.55, rad=0.0, dashed=False):
    ax.add_patch(FancyArrowPatch(
        start, end, arrowstyle="-|>", mutation_scale=11, linewidth=lw,
        color=color, linestyle="--" if dashed else "-", shrinkA=5,
        shrinkB=5, connectionstyle=f"arc3,rad={rad}"))


def make_figure() -> plt.Figure:
    fig, ax = plt.subplots(figsize=(16, 10.0))
    ax.set_xlim(0, 160)
    ax.set_ylim(0, 100)
    ax.axis("off")
    fig.patch.set_facecolor(PAGE)
    ax.set_facecolor(PAGE)

    # Header deliberately mirrors the original core-mechanism figure.
    ax.text(3, 94.0,
            "Core Mechanism: Qualify Persistent Permission, Compete for Access",
            fontsize=21.5, fontweight="bold", color=INK, family="DejaVu Sans")
    ax.text(3, 90.6,
            "SQCAD separates historical association from governance permission, then couples focus and decay under a fixed workspace budget",
            fontsize=9.9, color=MUTED, family="DejaVu Sans")
    ax.plot([3, 157], [88.9, 88.9], color="#C8D3DC", linewidth=1.0)

    # Three cases establish why association is not enough, without naming
    # implementation-level retrievers.
    box(ax, 5.5, 77.5, 43.5, 7.2, "Repeated Helpful Signal",
        "strong association + transferable contribution\n"
        "conditional use → qualified focus", GREEN, GREEN_BG, center=True,
        title_size=8.8, body_size=6.8)
    box(ax, 58.25, 77.5, 43.5, 7.2, "Self-Reinforcing Hitchhiker",
        "high co-occurrence + weak contribution\n"
        "no qualification → access decays in competition", RED, RED_BG,
        center=True, title_size=8.8, body_size=6.8)
    box(ax, 111.0, 77.5, 43.5, 7.2, "Rare High-Value Evidence",
        "low frequency + high-information qualification\n"
        "protected in scope · revalidate on shift", BLUE, BLUE_BG,
        center=True, title_size=8.8, body_size=6.8)

    # Core pipeline: only mechanism-level objects remain.
    box(ax, 7.0, 51.0, 23.0, 14.0, "Association Proposal",
        "association proposes candidates\n"
        "current-use support only\n"
        "no persistent permission", GRAY, GRAY_BG,
        title_size=9.0, body_size=7.8)

    diamond = Polygon([(34.0, 58.0), (43.0, 65.0), (52.0, 58.0),
                       (43.0, 51.0)], closed=True, facecolor=AMBER_BG,
                      edgecolor=AMBER, linewidth=1.9)
    ax.add_patch(diamond)
    ax.text(43, 59.2, "Scope Qualification", fontsize=9.0,
            fontweight="bold", color=INK, ha="center", va="center",
            family="DejaVu Sans")
    ax.text(43, 56.9, "positive · unresolved · negative\n"
            "scope + transport decide persistence", fontsize=7.0, color=MUTED,
            ha="center", va="center", linespacing=1.2, family="DejaVu Sans")

    box(ax, 56.0, 51.0, 37.5, 14.0, "Qualification-conditioned permission",
        "Q ∈ {q⁺, ?, q⁻}\n"
        "scope + transport decide persistence\n"
        "? remains neutral", PURPLE, PURPLE_BG, center=True,
        title_size=8.8, body_size=7.8, lw=1.75)

    box(ax, 101.5, 51.0, 39.0, 14.0, "Competitive Access Decay",
        "z = r + αq⁺ − βq⁻ − γd_scope − ηc\n"
        "budget projection:  Σᵢaᵢ = B\n"
        "focus and decay are one mechanism", PURPLE, PURPLE_BG,
        center=True, title_size=8.8, body_size=7.8, lw=1.75)

    arrow(ax, (30.3, 58.0), (33.7, 58.0), GRAY, lw=1.7)
    arrow(ax, (52.2, 58.0), (55.7, 58.0), AMBER, lw=1.8)
    arrow(ax, (93.8, 58.0), (101.2, 58.0), PURPLE, lw=1.8)

    # Three outcomes are the visible policy semantics.
    box(ax, 8.0, 33.0, 40.0, 9.0, "Protected Focus",
        "positive-qualified · matching scope\n"
        "no ordinary time/frequency decay\n"
        "access floor or qualification bonus", GREEN, GREEN_BG, center=True,
        title_size=9.1, body_size=7.8, lw=1.7)
    box(ax, 60.0, 33.0, 40.0, 9.0, "Bounded Conditional Access",
        "unresolved · strong query match · low risk\n"
        "temporary / conditional exposure\n"
        "no persistent state update", GRAY, GRAY_BG, center=True,
        title_size=9.1, body_size=7.8, lw=1.7)
    box(ax, 112.0, 33.0, 40.0, 9.0, "Scoped Attenuation",
        "negative-qualified or out-of-scope\n"
        "default veto / downweight / archive\n"
        "source evidence remains recoverable", RED, RED_BG, center=True,
        title_size=9.1, body_size=7.8, lw=1.7)

    arrow(ax, (119.0, 50.8), (28.0, 42.4), GREEN, lw=1.65, rad=0.16)
    arrow(ax, (121.0, 50.8), (80.0, 42.4), GRAY, lw=1.65, rad=0.03)
    arrow(ax, (124.0, 50.8), (132.0, 42.4), RED, lw=1.65, rad=-0.10)
    ax.text(121.5, 46.2, "one normalized budget projection",
            fontsize=7.0, color=PURPLE, ha="center", family="DejaVu Sans")

    # Single, spacious invariant strip.  The ledger/policy implementation
    # details remain in the method text, not in this mechanism figure.
    ax.add_patch(FancyBboxPatch(
        (9.0, 16.0), 142.0, 7.4,
        boxstyle="round,pad=0.02,rounding_size=0.18", facecolor=PURPLE_BG,
        edgecolor=PURPLE, linewidth=1.3))
    ax.text(80, 20.8,
            "EVIDENCE SURVIVES  ·  BELIEF IS SCOPED  ·  ACCESS CAN DECAY AND RECOVER",
            fontsize=8.7, fontweight="bold", color=PURPLE, ha="center",
            family="DejaVu Sans")
    ax.text(80, 18.2,
            "Unresolved evidence cannot change persistent access.  Access attenuation never deletes source evidence.",
            fontsize=7.7, color=MUTED, ha="center", family="DejaVu Sans")

    ax.text(3, 4.0,
            "Propose broadly  ·  qualify cautiously  ·  focus competitively",
            fontsize=7.8, color=MUTED, family="DejaVu Sans")
    fig.tight_layout(pad=0.35)
    return fig


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    fig = make_figure()
    outputs = [
        repo / "docs" / "assets" / "sqcad-core-mechanism-20260813",
        repo / "docs" / "docs_zn" / "03-核心问题与框架设计" / "框架图"
        / "12-SQCAD-Core-Mechanism",
    ]
    for base in outputs:
        base.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(base) + ".svg", format="svg")
        fig.savefig(str(base) + ".png", format="png", dpi=220)
        print(f"wrote {base}.svg / {base}.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
