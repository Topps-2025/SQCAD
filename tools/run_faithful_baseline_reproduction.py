"""Run the protocol-separated faithful baseline cores on a JSON contract.

The input schema is documented by the dataclasses in
``faithful_baseline_reproduction``: ``candidates`` is a list of memory records
and ``episodes`` is chronological.  CMI evaluator scores, when used for a
deterministic smoke run, belong in ``episode.cmi_scores`` with keys
``__none__``, ``with_memory`` and ``perturbed_memory``.  No future query or
lexical-overlap signal is manufactured by this tool.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from sqcad.faithful_baseline_reproduction import (
    CMIProtocol,
    DeMemProtocol,
    GovMemProtocol,
    MemoryWorthProtocol,
    TriviumProtocol,
    load_contract,
)


def _cmi_score(episode, memory_id: str, condition: str) -> float:
    """Read evaluator scores embedded in a contract for deterministic smoke runs."""
    values = episode.cmi_scores.get(memory_id if memory_id else "__none__", {})
    return float(values.get(condition, 0.0))


def run(path: Path) -> Dict[str, Any]:
    episodes, candidates = load_contract(path)
    return {
        "contract": str(path),
        "chronological_episode_ids": [e.episode_id for e in episodes],
        "baselines": {
            "cmi": CMIProtocol().run(episodes, candidates, _cmi_score).to_dict(),
            "memory_worth": MemoryWorthProtocol(alpha=1.0, beta=1.0,
                                                 budget=None).run(episodes, candidates).to_dict(),
            "demem": DeMemProtocol().run(episodes, candidates).to_dict(),
            "trivium": TriviumProtocol(probe_budget=1).run(episodes, candidates).to_dict(),
            "govmem": GovMemProtocol().run(episodes, candidates).to_dict(),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output),
                      "baselines": list(result["baselines"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
