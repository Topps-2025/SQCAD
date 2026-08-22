"""Content-addressed cache of completed LLM generations for long GPU runs.

Motivation (G-13, `40-` §6 item 2): the named-system reproduction pipelines
(ActMem, SimpleMem) make several LLM/GPU stages per trace.  A per-trace
checkpoint written after the last stage does not help when an intermediate
stage fails -- every generation already paid for in that trace is discarded.
On a cloud box with a finite generation budget that is exactly the failure
that wastes a long run.

Design, and why it is keyed on content:

  * The key is sha256(model, system, user prompt), NOT a trace/stage index.
    Every cached stage is a pure function of its prompt at temperature 0, so a
    content key stays correct when `--max-traces` changes, when the dataset is
    reordered, or when a resumed run reaches the same prompt from a different
    position.  An index key would mis-associate replies in all three cases.
  * Nothing about the pipeline's control flow is serialized or restored.  The
    re-run walks the same code path; prompts it already answered return from
    disk.  There is therefore no "restored state disagrees with recomputed
    state" failure mode.
  * Persistence is append-only JSONL, flushed and fsynced per entry.  A
    partially written trailing line from a kill fails to parse and is skipped
    on load, so an interrupt cannot corrupt the cache into unreadability.

Accounting discipline: a cache hit is a generation paid for by an earlier run,
not a new one.  Callers must keep hits OUT of the reported call/char counters
(those are cost claims) and report them separately.  See `VLLMClient.chat` in
`tools/repro_named_actmem.py`.

This caches generations only.  It is a cost artifact, never a result artifact,
and is never read by an evaluator.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Dict


class StageCache:
    """Append-only, crash-tolerant map from prompt hash to completed reply."""

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.hits = 0
        self.misses = 0
        self._mem: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._fh = None
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        needs_newline = False
        if path.exists():
            raw = path.read_text(encoding="utf-8")
            # A kill can leave a partial final line with no terminator.  It is
            # skipped below, but the next append would otherwise concatenate
            # onto it and destroy the NEW record too, so the terminator is
            # restored before reopening for append.
            needs_newline = bool(raw) and not raw.endswith("\n")
            for line in raw.splitlines():
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue          # truncated tail from an interrupt
                if isinstance(rec, dict) and "k" in rec and "v" in rec:
                    self._mem[rec["k"]] = rec["v"]
        self._fh = path.open("a", encoding="utf-8")
        if needs_newline:
            self._fh.write("\n")
            self._fh.flush()

    @staticmethod
    def key(model: str, system: str, user: str) -> str:
        h = hashlib.sha256()
        for part in (model, system, user):
            h.update(part.encode("utf-8"))
            h.update(b"\x00")
        return h.hexdigest()

    def get(self, k: str) -> str | None:
        with self._lock:
            v = self._mem.get(k)
            if v is None:
                self.misses += 1
            else:
                self.hits += 1
            return v

    def put(self, k: str, v: str) -> None:
        with self._lock:
            self._mem[k] = v
            if self._fh is not None:
                self._fh.write(json.dumps({"k": k, "v": v},
                                          ensure_ascii=False) + "\n")
                self._fh.flush()
                os.fsync(self._fh.fileno())

    def stats(self) -> dict:
        return {"path": str(self.path) if self.path else None,
                "entries": len(self._mem),
                "hits": self.hits, "misses": self.misses}

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
