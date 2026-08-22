"""Tests for the long-run stage cache (G-13: an interrupt must not discard
generations already paid for).

The regression these tests exist for: tolerating a truncated tail line on READ
is not enough.  A killed write leaves a half line with no terminator, so the
next append concatenates onto it and destroys the NEW record too -- one entry
lost from before the crash and one from after it.
"""

import json

from src.sqcad.stage_cache import StageCache


def _put(path, n_start, n_end):
    c = StageCache(path)
    for i in range(n_start, n_end):
        c.put(StageCache.key("m", "s", f"u{i}"), f"v{i}")
    c.close()


def _truncate_last_line(path):
    """Emulate a kill mid-write: drop the terminator and part of the payload."""
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    kept = "\n".join(lines[:-1]) + "\n" if len(lines) > 1 else ""
    path.write_text(kept + lines[-1][: len(lines[-1]) // 2], encoding="utf-8")


def test_key_is_content_addressed(tmp_path):
    k = StageCache.key("m", "s", "u")
    assert StageCache.key("m", "s", "u") == k
    assert StageCache.key("other-model", "s", "u") != k
    assert StageCache.key("m", "other-system", "u") != k
    assert StageCache.key("m", "s", "other-user") != k
    # the field separator must prevent boundary collisions
    assert StageCache.key("m", "s", "u") != StageCache.key("ms", "", "u")


def test_entries_survive_process_restart(tmp_path):
    path = tmp_path / "cache.jsonl"
    _put(path, 0, 3)
    c = StageCache(path)
    assert c.get(StageCache.key("m", "s", "u1")) == "v1"
    assert c.hits == 1 and c.misses == 0
    assert c.get(StageCache.key("m", "s", "absent")) is None
    assert c.misses == 1
    c.close()


def test_truncated_tail_is_skipped_not_resurrected(tmp_path):
    path = tmp_path / "cache.jsonl"
    _put(path, 0, 3)
    _truncate_last_line(path)
    c = StageCache(path)
    # the two intact records still load; the truncated one is simply absent
    assert c.get(StageCache.key("m", "s", "u0")) == "v0"
    assert c.get(StageCache.key("m", "s", "u1")) == "v1"
    assert c.stats()["entries"] == 2
    c.close()


def test_append_after_truncated_tail_does_not_lose_the_new_record(tmp_path):
    """The G-13 regression: without repairing the missing terminator, the
    first record written by the resumed run is concatenated onto the half
    line and lost as well."""
    path = tmp_path / "cache.jsonl"
    _put(path, 0, 3)
    _truncate_last_line(path)
    _put(path, 9, 10)                     # the resumed run's first generation

    c = StageCache(path)
    assert c.get(StageCache.key("m", "s", "u9")) == "v9"
    assert c.stats()["entries"] == 3      # 2 intact + 1 new
    c.close()
    # The orphaned half line stays on disk (it is unrecoverable) but is now
    # terminated, so it is confined to ONE bad line instead of absorbing the
    # record appended after it.
    bad = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError:
            bad += 1
    assert bad == 1


def test_repeated_kills_never_lose_a_completed_record(tmp_path):
    path = tmp_path / "cache.jsonl"
    _put(path, 0, 3)
    counts = []
    for i in (9, 10):
        _truncate_last_line(path)
        _put(path, i, i + 1)
        c = StageCache(path)
        counts.append(c.stats()["entries"])
        assert c.get(StageCache.key("m", "s", f"u{i}")) == f"v{i}"
        c.close()
    # 3 -> truncate(2) + 1 = 3 -> truncate(2) + 1 = 3: every record written
    # after a kill survives the next kill/reopen cycle.
    assert counts == [3, 3]


def test_hits_and_misses_are_counted_separately(tmp_path):
    """Callers report hits OUTSIDE the LLM call counters (those are cost
    claims), so the two must not be conflated."""
    path = tmp_path / "cache.jsonl"
    c = StageCache(path)
    k = StageCache.key("m", "s", "u")
    assert c.get(k) is None
    c.put(k, "v")
    assert c.get(k) == "v"
    st = c.stats()
    assert st["hits"] == 1 and st["misses"] == 1 and st["entries"] == 1
    assert st["path"] == str(path)
    c.close()


def test_disabled_cache_is_a_no_op(tmp_path):
    """Not passing --stage-cache must leave the frozen-contract behaviour
    bit-for-bit unchanged, with no file side effects."""
    c = StageCache(None)
    k = StageCache.key("m", "s", "u")
    c.put(k, "v")
    assert c.get(k) == "v"                # in-memory only, within one process
    assert c.stats()["path"] is None
    c.close()
    assert list(tmp_path.iterdir()) == []
