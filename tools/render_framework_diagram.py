"""Render the SQCAD framework engineering diagram (v2026-08-13).

Deterministic matplotlib rendering of the current frozen framework design,
aligned with docs/自用/01-research-gap/研究逻辑与理论证明/14-* 16.9-16.10 (Evidence censorship
awareness, Qualification-as-authorization, Access with restore/probe,
Decision with identification sets) and the frozen source code:

    Evidence    -> src/sqcad/causal_memory_store.py
    Qualification -> src/sqcad/score_semantic_gate_a.py,
                    src/sqcad/decision_identification_theory.py
    Access      -> src/sqcad/unified_baseline_runner.py (_gated_score,
                   budget projection)
    Decision    -> src/sqcad/decision_identification_theory.py
                   (governance_choice / r_star)
    Lifecycle   -> src/sqcad/cost_contract_experiment.py,
                   src/sqcad/self_obscuring_ablation.py

Outputs (SVG + PNG):
    docs/assets/sqcad-framework-20260813.{svg,png}   (English, for GitHub)
    docs/docs_zn/03-核心问题与框架设计/框架图/13-SQCAD-Framework-20260813.{svg,png}

Style follows the existing 11-/12-SQCAD renders (matplotlib, same palette).
Run:  PYTHONPATH=src python tools/render_framework_diagram.py
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon
from pathlib import Path

# palette shared with the existing renders
TEAL = "#2d7e83";   TEAL_BG = "#e8f6f6"
AMBER = "#b66a00";  AMBER_BG = "#fff2d9"
PURPLE = "#7a49a5"; PURPLE_BG = "#f4eaff"
BLUE = "#3c78b5";   BLUE_BG = "#eaf3ff"
GREEN = "#33845a";  GREEN_BG = "#eaf7ee"
RED = "#b54d4d";    RED_BG = "#fff0f0"
GRAY = "#6c7b88";   GRAY_BG = "#f0f3f6"
INK = "#17324a";    MUTED = "#596e80"
BG = "#fbfcfe";     BORDER = "#c8d3dc"


def box(ax, x, y, w, h, fc, ec, lw=1.35, r=0.0):
    style = "round,pad=0.02,rounding_size=0.08"
    return ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle=style, fc=fc, ec=ec, lw=lw))


def text(ax, x, y, s, size=8, weight="normal", color=INK, ha="left",
         va="center"):
    ax.text(x, y, s, fontsize=size, fontweight=weight, color=color,
            ha=ha, va=va, family="DejaVu Sans")


def title_block(ax, x, y, s, sub):
    text(ax, x, y + 28, s, size=21, weight="bold", color=INK)
    text(ax, x, y + 9, sub, size=10.5, color=MUTED)


def band_label(ax, x, y, s, sub, color):
    """Left rail label for one layer."""
    text(ax, x, y + 20, s, size=9.5, weight="bold", color=color, ha="center")
    text(ax, x, y + 2, sub, size=6.3, color=MUTED, ha="center")


def arrow(ax, x1, y1, x2, y2, color=GRAY, lw=1.4, dashed=False):
    ax.add_patch(FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=10,
        color=color, lw=lw,
        linestyle=(0, (4.5, 2.0)) if dashed else "solid"))


def make_figure() -> plt.Figure:
    W, H = 14.4, 10.4
    fig, ax = plt.subplots(figsize=(W, H))
    ax.set_xlim(0, 144)
    ax.set_ylim(0, 104)
    ax.axis("off")
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    title_block(ax, 3, 96,
                "Scope-Qualified Competitive Access Decay (SQCAD)",
                "Propose broadly  ·  qualify cautiously  ·  focus "
                "competitively  |  evidence survives, belief is scoped, "
                "access can decay and recover")

    # -- layer bands ---------------------------------------------------------
    layers = [
        ("EVIDENCE",   "censoring-aware\nrecords", TEAL,   TEAL_BG),
        ("QUALIFICATION", "point · bound ·\nunresolved · mismatch",
         AMBER, AMBER_BG),
        ("ACCESS",     "fixed-budget\nfocus & decay", PURPLE, PURPLE_BG),
        ("DECISION",   "cost-aware\nauthorization", BLUE,  BLUE_BG),
        ("LIFECYCLE",  "execution · feedback\nrevalidation", GREEN, GREEN_BG),
    ]
    band_y = {"EVIDENCE": 78.0, "QUALIFICATION": 62.0, "ACCESS": 46.0,
              "DECISION": 30.0, "LIFECYCLE": 13.0}
    for name, sub, color, bg in layers:
        y = band_y[name]
        ax.add_patch(FancyBboxPatch(
            (2.0, y), 8.2, 11.4,
            boxstyle="round,pad=0.02,rounding_size=0.08", fc=bg,
            ec=BORDER, lw=0.8))
        band_label(ax, 6.1, y + 1.4, name, sub, color)

    # -- EVIDENCE row ---------------------------------------------------------
    ev = band_y["EVIDENCE"]
    ev_boxes = [
        ("Chronological candidate stream", "frozen per step · future "
         "leakage forbidden", 15, ev + 4.4, 19, 5.4, TEAL, TEAL_BG),
        ("Source & derived lineage", "source deletion explains derived "
         "memory", 36, ev + 4.4, 19, 5.4, TEAL, TEAL_BG),
        ("Scope · version · exposure", "support, silence duration, "
         "exposure probability", 57, ev + 4.4, 19, 5.4, TEAL, TEAL_BG),
        ("Restore & revalidation history", "probe results, correction "
         "events", 78, ev + 4.4, 19, 5.4, TEAL, TEAL_BG),
        ("Association proposal", "BM25 · dense · recency · outcome "
         "co-occurrence", 99, ev + 4.4, 21, 5.4, GRAY, GRAY_BG),
    ]
    for label, sub, x, y, w, h, ec, fc in ev_boxes:
        box(ax, x, y, w, h, fc, ec, lw=1.3)
        text(ax, x + 1.0, y + h - 1.6, label, size=7.4, weight="bold")
        text(ax, x + 1.0, y + 1.5, sub, size=6.0, color=MUTED)
    text(ax, 15, ev + 0.4,
         "Evidence silence is not low value: archive-induced starvation "
         "must be distinguishable from true non-value.",
         size=6.6, color=TEAL)

    # -- QUALIFICATION row -----------------------------------------------------
    qy = band_y["QUALIFICATION"]
    diamond = Polygon(
        [(62, qy + 10.6), (68, qy + 14.2), (62, qy + 17.8), (56, qy + 14.2)],
        closed=True, fc=AMBER_BG, ec=AMBER, lw=1.8)
    ax.add_patch(diamond)
    text(ax, 62, qy + 14.2, "Scope\nQualification", size=6.8,
         weight="bold", ha="center")
    q_boxes = [
        ("support · shift · overlap", 22, qy + 4.2, 18, 5.2, TEAL, TEAL_BG),
        ("provenance · evidence level", 42, qy + 4.2, 18, 5.2, GRAY, GRAY_BG),
        ("Q(i,s) ∈ {point, bound,\nunresolved, mismatch}", 72, qy + 4.2,
         22, 5.2, AMBER, AMBER_BG),
        ("identification set\ncrosses action boundary?", 96, qy + 4.2,
         20, 5.2, BLUE, BLUE_BG),
    ]
    for label, x, y, w, h, ec, fc in q_boxes:
        box(ax, x, y, w, h, fc, ec, lw=1.3)
        text(ax, x + 1.0, y + h / 2, label, size=6.4, ha="left")
    text(ax, 22, qy + 0.4,
         "Only qualified evidence may change persistent access policy; "
         "unresolved evidence cannot decay into negative belief.",
         size=6.6, color=AMBER)
    # arrows within the row
    arrow(ax, 40, qy + 14.2, 55.6, qy + 14.2, color=TEAL)
    arrow(ax, 68.4, qy + 14.2, 84, qy + 8.6, color=AMBER)
    arrow(ax, 68.4, qy + 14.2, 84, qy + 19.0, color=AMBER)

    # -- ACCESS row -------------------------------------------------------------
    ay = band_y["ACCESS"]
    a_boxes = [
        ("keep", "positive-qualified · protected in scope", 15, ay + 4.4,
         15, 5.4, PURPLE, PURPLE_BG),
        ("downweight", "negative-qualified or out-of-scope", 32, ay + 4.4,
         15, 5.4, PURPLE, PURPLE_BG),
        ("archive", "reversible · source evidence never erased", 49,
         ay + 4.4, 17, 5.4, PURPLE, PURPLE_BG),
        ("restore / probe", "paid channel · cost & latency recorded · "
         "breaks self-obscuring loop", 68, ay + 4.4, 23, 5.4, RED, RED_BG),
        ("budget projection", "a = B · Project(z/T),  Σaᵢ = B", 93,
         ay + 4.4, 24, 5.4, PURPLE, PURPLE_BG),
    ]
    for label, sub, x, y, w, h, ec, fc in a_boxes:
        box(ax, x, y, w, h, fc, ec, lw=1.3)
        text(ax, x + 1.0, y + h - 1.6, label, size=7.2, weight="bold")
        text(ax, x + 1.0, y + 1.3, sub, size=5.8, color=MUTED)
    text(ax, 15, ay + 1.2,
         "z = r + αq⁺ − βq⁻ − γd_scope − ηc       "
         "focus and decay are one budget-reallocation mechanism",
         size=6.6, color=PURPLE)
    arrow(ax, 84, ay + 9.8, 92.6, ay + 7.1, color=PURPLE)
    arrow(ax, 84, ay + 9.8, 92.6, ay + 2.6, color=PURPLE)

    # -- DECISION row ------------------------------------------------------------
    dy = band_y["DECISION"]
    box(ax, 15, dy + 4.4, 34, 5.4, BLUE_BG, BLUE, lw=1.8)
    text(ax, 16, dy + 8.2, "Commit requires provable qualification",
         size=7.6, weight="bold", color=BLUE)
    text(ax, 16, dy + 6.0,
         "identification set does not cross the action boundary,",
         size=6.0, color=MUTED)
    text(ax, 16, dy + 4.0,
         "or the three-way cost comparison selects commit:",
         size=6.0, color=MUTED)
    box(ax, 51, dy + 4.4, 33, 5.4, BLUE_BG, BLUE, lw=1.3)
    text(ax, 52, dy + 7.6,
         "min{ R*(L,U),  C_defer,  C_probe + R*_after }",
         size=7.2, weight="bold", color=INK)
    text(ax, 52, dy + 5.4,
         "probing has a fundamental information price "
         "(Thm 3/4, doc 16)",
         size=6.0, color=MUTED)
    box(ax, 86, dy + 4.4, 31, 5.4, GRAY_BG, GRAY, lw=1.3)
    text(ax, 87, dy + 8.2, "defer / keep unresolved", size=7.2,
         weight="bold")
    text(ax, 87, dy + 6.0, "bounded fallback access allowed;", size=6.0,
         color=MUTED)
    text(ax, 87, dy + 4.0, "no persistent positive or negative update",
         size=6.0, color=MUTED)
    arrow(ax, 49.4, dy + 7.1, 50.6, dy + 7.1, color=BLUE)
    arrow(ax, 84.4, dy + 7.1, 85.6, dy + 7.1, color=GRAY)

    # -- LIFECYCLE row + feedback loops -------------------------------------------
    ly = band_y["LIFECYCLE"]
    l_boxes = [
        ("execution & outcome", "utility · cost · risk recorded", 15,
         ly + 3.8, 19, 5.0, GREEN, GREEN_BG),
        ("future candidate stream", "regenerated after every persistent "
         "action", 36, ly + 3.8, 19, 5.0, GREEN, GREEN_BG),
        ("correction events", "reopen archived evidence; revalidation on "
         "scope/version shift", 57, ly + 3.8, 25, 5.0, GREEN, GREEN_BG),
        ("lifecycle ledger", "net benefit · false forgetting · harmful "
         "retention · recovery latency", 84, ly + 3.8, 33, 5.0, GREEN,
         GREEN_BG),
    ]
    for label, sub, x, y, w, h, ec, fc in l_boxes:
        box(ax, x, y, w, h, fc, ec, lw=1.3)
        text(ax, x + 1.0, y + h - 1.5, label, size=7.0, weight="bold")
        text(ax, x + 1.0, y + 1.2, sub, size=5.8, color=MUTED)
    # feedback loop from lifecycle back to evidence (left and right rails)
    arrow(ax, 15, ly + 8.8, 8.4, 26.4, color=GREEN, dashed=True)
    arrow(ax, 8.4, 26.4, 8.4, ev + 8.8, color=GREEN, dashed=True)
    arrow(ax, 8.4, ev + 8.8, 14.6, ev + 8.8, color=GREEN, dashed=True)
    arrow(ax, 105, ly + 6.3, 134, 20.0, color=GREEN, dashed=True)
    arrow(ax, 134, 20.0, 134, ev + 8.8, color=GREEN, dashed=True)
    arrow(ax, 134, ev + 8.8, 120.6, ev + 8.8, color=GREEN, dashed=True)

    # -- bottom strip: the ten design conditions (doc 14, 16.10) -------------------
    strip = ("Ten required conditions: treatment fidelity · candidate/"
             "evidence accounting · lineage preservation · decision "
             "identification · censoring awareness · recovery channel · "
             "cost-aware authorization · interference awareness · "
             "scope/version conditioning · reversibility & auditability")
    ax.add_patch(FancyBboxPatch(
        (3.0, 1.0), 138.0, 3.6,
        boxstyle="round,pad=0.02,rounding_size=0.08", fc=BG,
        ec=BORDER, lw=0.8))
    text(ax, 72, 2.8, strip, size=6.4, color=MUTED, ha="center")

    return fig


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    fig = make_figure()
    fig.tight_layout(pad=0.4)

    outputs = [
        repo / "docs" / "assets" / "sqcad-framework-20260813",
        repo / "docs" / "docs_cn" / "03-核心问题与框架设计" / "框架图"
              / "13-SQCAD-Framework-20260813",
    ]
    for base in outputs:
        base.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(base) + ".svg", format="svg")
        fig.savefig(str(base) + ".png", format="png", dpi=200)
        print(f"wrote {base}.svg / .png")
    plt.close(fig)


if __name__ == "__main__":
    main()
