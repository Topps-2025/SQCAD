"""Runnable baseline controllers for LifecycleBench-v3.

Every rule here reads ``public.jsonl`` only -- no hidden field, no oracle, no
future.  Three rules are provided, and the contrast between them is the point:

``relevance``
    Keep whatever overlaps the visible query.  This is the instinct the
    score-fiber theorem predicts will fail, and it does.

``qualify``
    The SQCAD qualification core: archive on scope mismatch or on visible
    negative evidence (an ``update``/``correction`` event touching the item),
    otherwise keep.  With lineage checking disabled this reproduces the frozen
    ``sqcad_cert`` reference row exactly (value -7.1892, regret 9.2162).

``qualify_lineage``
    The same rule plus a lineage-conflict check: if a co-scoped counterpart
    covers the same content and no visible event has already resolved it, the
    item is superseded rather than independently qualified, so archive.  This is
    the mechanism the paper reports as decisive.

Usage::

    python example_controller.py --rule qualify_lineage --out actions.json
    python score.py --actions actions.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TOKEN_RE = re.compile(r"[a-z0-9]+")

# A visible event re-qualifies an item when it shares this many content tokens.
EVENT_OVERLAP = 2
# Two facts are lineage counterparts at this much shared content.
LINEAGE_OVERLAP = 3
# Query adoption threshold used by the relevance contrast.
ADOPT_OVERLAP = 2

EVENT_KINDS = ("update", "correction")


def toks(text: str) -> set[str]:
    return set(TOKEN_RE.findall(str(text).lower()))


def _events(row: dict[str, Any]) -> list[set[str]]:
    """Token sets of every visible update/correction message."""
    return [toks(msg.get("text", ""))
            for sess in row.get("sessions", [])
            for msg in sess.get("messages", [])
            if msg.get("kind") in EVENT_KINDS]


def _event_resolved(item_tokens: set[str], events: list[set[str]]) -> bool:
    return any(len(ev & item_tokens) >= EVENT_OVERLAP for ev in events)


def decide_qualify(row: dict[str, Any], lineage: bool = True) -> str:
    """Observable qualification: keep only while the item stays qualified."""
    fid = row.get("decision_memory")
    scope = row.get("decision_scope")
    memories = row.get("memories", [])
    target = next((m for m in memories if m.get("fid") == fid), None)
    if target is None:
        return "archive"

    # MISMATCH: the item is not valid in the scope making the decision.
    if target.get("scope") not in {scope, "any"}:
        return "archive"

    target_tokens = toks(target.get("text", ""))
    events = _events(row)

    # NEGATIVE: a visible correction/update already retired this content.
    if _event_resolved(target_tokens, events):
        return "archive"

    # UNRESOLVED via lineage: a live co-scoped counterpart covers the same
    # slot, so this item is superseded rather than independently supported.
    if lineage:
        for other in memories:
            if other.get("fid") == fid or not other.get("introduced", True):
                continue
            if other.get("scope") != target.get("scope"):
                continue
            other_tokens = toks(other.get("text", ""))
            if len(other_tokens & target_tokens) < LINEAGE_OVERLAP:
                continue
            # An event-resolved counterpart is dead; it does not supersede us.
            if _event_resolved(other_tokens, events):
                continue
            return "archive"

    return "keep"


def decide_qualify_no_lineage(row: dict[str, Any]) -> str:
    return decide_qualify(row, lineage=False)


def decide_relevance(row: dict[str, Any]) -> str:
    """Contrast: keep whatever looks relevant to the visible query."""
    fid = row.get("decision_memory")
    query = toks(row.get("decision_task", {}).get("query", ""))
    target = next((m for m in row.get("memories", []) if m.get("fid") == fid), None)
    if target is None or not query:
        return "archive"
    hit = len(query & toks(target.get("text", "")))
    return "keep" if hit >= ADOPT_OVERLAP else "archive"


RULES = {
    "relevance": decide_relevance,
    "qualify": decide_qualify_no_lineage,
    "qualify_lineage": decide_qualify,
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rule", choices=sorted(RULES), default="qualify_lineage")
    ap.add_argument("--data", type=Path, default=HERE)
    ap.add_argument("--out", type=Path, default=Path("actions.json"))
    args = ap.parse_args()

    decide = RULES[args.rule]
    with (args.data / "public.jsonl").open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]

    actions = {row["episode_id"]: decide(row) for row in rows}
    args.out.write_text(json.dumps(actions, indent=2), encoding="utf-8")

    keeps = sum(1 for a in actions.values() if a == "keep")
    print(f"rule={args.rule}  worlds={len(actions)}  "
          f"keep={keeps}  archive={len(actions) - keeps}")
    print(f"wrote {args.out}\n\nnow run:  python score.py --actions {args.out}")


if __name__ == "__main__":
    main()
