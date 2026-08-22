"""R6 blind judge: score the anchor cases with an LLM over an OpenAI-compatible
endpoint, writing only `case,judgment` so `tools/r6_anchor_kappa.py` can score
it against the private oracle labels.

Blindness contract (what makes this an anchor rather than a self-check):
  * the prompt carries ONLY the case body from `anchor_cases.md`, which contains
    no oracle label, no episode id, and no mechanism-family name;
  * `anchor_labels_private.csv` is never opened by this script;
  * cases are presented in a shuffled order under a fixed seed, so ordinal
    position cannot leak the family grouping that the export's case numbering
    otherwise reveals (families run in contiguous pairs);
  * decoding is greedy (temperature 0) so the batch is reproducible.

The 7 byte-identical case pairs (see `r6_anchor_kappa.py`) are deliberately
BOTH sent.  Their answers are expected to agree, and a disagreement inside an
identical pair is a direct read on judge noise -- it is reported as
`identical_pair_inconsistency`, which is a free reliability diagnostic the
duplication happens to buy back.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List

CASES = Path("remote_results/lifecycle_audit/r6_anchor/anchor_cases.md")
OUT_DEFAULT = Path("remote_results/lifecycle_audit/r6_anchor/judge_labels.csv")
RAW_DEFAULT = Path("remote_results/lifecycle_audit/r6_anchor/judge_raw.json")

CASE_RE = re.compile(r"(?mi)^#+\s*case\s*(\d+)")
CLASSES = ("keep", "archive", "neutral")

SYSTEM_CALIBRATED = (
    "You are an expert annotator for an agent-memory governance benchmark. "
    "For each case you see one or two sessions of dialogue, a decision task, "
    "one decision memory, and the ten future task slots that will follow. "
    "Decide what should happen to the DECISION MEMORY.\n\n"
    "The benchmark scores a memory by the total value it produces over the ten "
    "future slots: a slot that needs the memory and has it earns value, a "
    "memory that is stale, wrong-scope, or superseded and still gets adopted "
    "costs a large penalty, and merely storing or exposing a memory costs a "
    "little. Let D be (value if kept) minus (value if archived).\n\n"
    "Answer 'keep' if D is clearly positive; 'archive' if D is clearly "
    "negative; 'neutral' if |D| is small -- which is the correct answer "
    "whenever no future slot actually needs this memory and it also does no "
    "harm, so keeping and archiving differ only by a negligible storage cost. "
    "'neutral' is a real and reasonably common answer here; do not avoid it.\n\n"
    "Check in order: (1) does any of the ten slots actually need this memory? "
    "(2) has a later session superseded or contradicted it? (3) is its scope "
    "the same as the slots' scope? (4) would adopting it cause a wrong answer?"
    "\n\nReply with a single word: keep, archive, or neutral. No explanation."
)

SYSTEM = (
    "You are an expert annotator for an agent-memory governance benchmark. "
    "For each case you see two sessions of dialogue, a decision task, one "
    "decision memory, and the ten future task slots that will follow. You must "
    "decide what should happen to the DECISION MEMORY.\n\n"
    "Answer 'keep' if retaining the memory produces more total future value "
    "than archiving it; 'archive' if archiving produces more; 'neutral' if the "
    "two are close enough that neither is clearly better.\n\n"
    "Consider: whether the memory is still correct or has been superseded by a "
    "later session; whether it is in the right scope for the future tasks; "
    "whether it will actually be needed by a future slot; and whether keeping "
    "it crowds out something more useful.\n\n"
    "Reply with a single word: keep, archive, or neutral. No explanation."
)


def parse_cases(path: Path) -> Dict[int, str]:
    parts = CASE_RE.split(path.read_text(encoding="utf-8"))
    return {int(parts[i]): parts[i + 1].strip()
            for i in range(1, len(parts), 2)}


def strip_prompt_tail(body: str) -> str:
    """Remove the human-facing answer line so it is not fed to the model."""
    return re.sub(r"(?mi)^\*\*Your judgment\*\*.*$", "", body).strip()


PROMPTS = {"terse": SYSTEM, "calibrated": SYSTEM_CALIBRATED}


def call(base: str, model: str, body: str, timeout: int,
         max_tokens: int, system: str = SYSTEM) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": body}],
        "temperature": 0.0,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(
        f"{base.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer local"})
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        got = json.loads(fh.read())
    return got["choices"][0]["message"]["content"]


def extract(text: str) -> str | None:
    """Pull the verdict out of the reply.  Returns None when the reply does not
    contain exactly one class word -- an unparseable reply is recorded as such
    rather than silently coerced to a class."""
    low = text.lower()
    hits = [c for c in CLASSES if re.search(rf"\b{c}\b", low)]
    if len(hits) == 1:
        return hits[0]
    # A reply may restate the options then commit; take the last mention only
    # when one class clearly trails the others.
    pos = {c: low.rfind(c) for c in CLASSES if c in low}
    if pos:
        last = max(pos, key=lambda c: pos[c])
        others = [p for c, p in pos.items() if c != last]
        if all(pos[last] - o > 8 for o in others):
            return last
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", type=Path, default=CASES)
    ap.add_argument("--base", default="http://127.0.0.1:8000/v1")
    ap.add_argument("--model", default="qwen3-8b")
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--raw", type=Path, default=RAW_DEFAULT)
    ap.add_argument("--seed", type=int, default=20260823)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--max-tokens", type=int, default=16)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--prompt", choices=sorted(PROMPTS), default="terse",
                    help="which pre-declared system prompt to use; both are "
                         "kept in the script so a reported batch names its "
                         "prompt instead of silently replacing it")
    args = ap.parse_args()
    system = PROMPTS[args.prompt]

    cases = parse_cases(args.cases)
    order = sorted(cases)
    random.Random(args.seed).shuffle(order)   # break family-contiguous ordering

    raw: List[Dict[str, object]] = []
    labels: Dict[int, str] = {}
    for n, cid in enumerate(order, 1):
        body = strip_prompt_tail(cases[cid])
        verdict, text, err = None, "", None
        for attempt in range(args.retries + 1):
            try:
                text = call(args.base, args.model, body, args.timeout,
                            args.max_tokens, system)
                verdict = extract(text)
                if verdict:
                    break
            except (urllib.error.URLError, OSError, KeyError,
                    json.JSONDecodeError) as exc:
                err = f"{type(exc).__name__}: {exc}"
        raw.append({"case": cid, "presented_position": n,
                    "reply": text, "verdict": verdict, "error": err})
        if verdict:
            labels[cid] = verdict
        print(f"[{n}/{len(order)}] case {cid}: "
              f"{verdict or 'UNPARSED ' + (err or repr(text)[:60])}",
              flush=True)

    args.raw.parent.mkdir(parents=True, exist_ok=True)
    args.raw.write_text(json.dumps(
        {"model": args.model, "seed": args.seed,
         "presentation_order": order,
         "prompt_variant": args.prompt,
         "system_prompt": system,
         "decoding": {"temperature": 0.0, "max_tokens": args.max_tokens},
         "blindness": ("prompt carries only the case body with the judgment "
                       "line stripped; oracle labels never read by this "
                       "script; order shuffled to break family contiguity"),
         "results": raw}, indent=2, ensure_ascii=False), encoding="utf-8")

    with args.out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["case", "judgment"])
        for cid in sorted(labels):
            w.writerow([cid, labels[cid]])

    unparsed = [r["case"] for r in raw if not r["verdict"]]
    print(f"\nparsed {len(labels)}/{len(order)}")
    if unparsed:
        print(f"UNPARSED cases (excluded from the CSV): {unparsed}")
    print(f"wrote {args.out} and {args.raw}")
    return 0 if labels else 1


if __name__ == "__main__":
    sys.exit(main())
