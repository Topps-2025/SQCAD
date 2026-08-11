"""Conservative, query-independent POS/regex decomposition baseline for Gate A.

This program is deliberately a *negative control* rather than a semantic or
causal parser.  It reads only packet evidence sessions and emits auditable
candidate factors/relations.  It never reads ``question``, ``adjudication_only``
or any gold annotation field.  The raw evidence remains the primary store;
the emitted annotation is a removable sidecar.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple


WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")
SENTENCE_RE = re.compile(r"[^.!?\n]+(?:[.!?]+|$)", re.MULTILINE)
TIME_RE = re.compile(
    r"\b(?:\d{1,2}(?::\d{2})?\s?(?:am|pm)|\d{4}[-/]\d{1,2}[-/]\d{1,2}|"
    r"(?:yesterday|today|tomorrow|last|next|this)\s+\w+|\w+\s+\d{1,2}(?:st|nd|rd|th)?(?:,\s*\d{4})?)\b",
    re.IGNORECASE,
)
NEGATION = {"not", "never", "no", "n't", "cannot", "can't", "without", "avoid", "avoids", "avoided"}
PREFERENCE = {"prefer", "prefers", "preferred", "like", "likes", "love", "loves", "want", "wants", "avoid", "avoids"}
TOOL_WORDS = {"api", "tool", "browser", "database", "python", "shell", "terminal", "model", "search"}
SKIP_AUX = {"do", "does", "did", "have", "has", "had", "can", "could", "may", "might", "must", "shall", "should", "will", "would", "be", "am", "is", "are", "was", "were", "been", "being"}
MAX_SPANS = 384
MAX_FACTORS = 768
MAX_RELATIONS = 768
COMMON_VERBS = {"buy", "bought", "use", "used", "call", "called", "eat", "ate", "work", "works", "worked", "need", "needs", "want", "wants", "prefer", "prefers", "like", "likes", "avoid", "avoids", "update", "updated", "change", "changed", "enable", "enabled", "produce", "produced", "fail", "failed", "succeed", "succeeded", "recommend", "recommended", "remember", "forgot", "forget"}


def heuristic_tags(tokens: Sequence[str]) -> List[Tuple[str, str]]:
    """Small deterministic POS proxy used to keep the negative control local."""
    tags: List[Tuple[str, str]] = []
    for token in tokens:
        lower = token.lower()
        if lower in COMMON_VERBS or lower in SKIP_AUX or lower.endswith(("ed", "ing")):
            tag = "VB"
        elif token[:1].isupper():
            tag = "NNP"
        elif lower.endswith(("ous", "ive", "al", "ful", "less", "able", "ic")):
            tag = "JJ"
        elif lower in {"i", "you", "he", "she", "we", "they", "it", "my", "your", "their", "our"}:
            tag = "PRP"
        else:
            tag = "NN"
        tags.append((token, tag))
    return tags


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def sentence_spans(text: str) -> Iterable[Tuple[int, int, str]]:
    for match in SENTENCE_RE.finditer(text):
        start, end = match.span()
        value = match.group(0).strip()
        if not value:
            continue
        leading = len(match.group(0)) - len(match.group(0).lstrip())
        start += leading
        yield start, end, text[start:end]


def token_offsets(text: str) -> List[Tuple[str, int, int]]:
    return [(m.group(0), m.start(), m.end()) for m in WORD_RE.finditer(text)]


def norm(value: str) -> str:
    return " ".join(value.lower().split())


def scope_for_role(role: str) -> str | None:
    return "user" if role == "user" else "assistant" if role == "assistant" else None


def factor(
    factor_id: str,
    factor_type: str,
    normalized_form: str,
    span_id: str,
    role: str,
    polarity: str = "positive",
    temporal_scope: str | None = None,
) -> Dict[str, object]:
    return {
        "factor_id": factor_id,
        "factor_type": factor_type,
        "normalized_form": norm(normalized_form),
        "span_ids": [span_id],
        "subject_scope": scope_for_role(role),
        "task_scope": None,
        "temporal_scope": temporal_scope,
        "polarity": polarity,
        "evidential_status": "explicit",
    }


def extract_packet(packet: Mapping[str, object], pos_tag_sents: object) -> Dict[str, object]:
    """Generate deterministic sidecar candidates without gold/query access."""
    spans: List[Dict[str, object]] = []
    factors: List[Dict[str, object]] = []
    relations: List[Dict[str, object]] = []
    span_counter = 0
    factor_counter = 0

    def add_span(session_id: str, turn_index: int, start: int, end: int, text: str, role: str) -> str:
        nonlocal span_counter
        if span_counter >= MAX_SPANS:
            return ""
        span_counter += 1
        span_id = f"sp_{span_counter:05d}"
        spans.append({
            "span_id": span_id,
            "session_id": session_id,
            "turn_index": turn_index,
            "char_start": start,
            "char_end": end,
            "text": text,
            "role": role,
        })
        return span_id

    def add_factor(ftype: str, form: str, span_id: str, role: str, polarity: str = "positive", temporal: str | None = None) -> str:
        nonlocal factor_counter
        if factor_counter >= MAX_FACTORS or not span_id:
            return ""
        factor_counter += 1
        fid = f"fa_{factor_counter:05d}"
        factors.append(factor(fid, ftype, form, span_id, role, polarity, temporal))
        return fid

    for session in packet["evidence_sessions"]:
        session_id = str(session["session_id"])
        for turn_index, turn in enumerate(session["turns"]):
            content, role = str(turn["content"]), str(turn["role"])
            for start, end, sentence in sentence_spans(content):
                span_id = add_span(session_id, turn_index, start, end, sentence, role)
                if not span_id:
                    continue
                offsets = token_offsets(sentence)
                if not offsets:
                    continue
                tokens = [token for token, _, _ in offsets]
                tagged = pos_tag_sents([tokens])[0] if pos_tag_sents is not None else heuristic_tags(tokens)
                lower = [token.lower() for token in tokens]
                negated = any(token in NEGATION for token in lower)
                polarity = "negative" if negated else "positive"
                temporal = next((token for token in lower if TIME_RE.fullmatch(token)), None)
                time_match = TIME_RE.search(sentence)
                if time_match:
                    time_form = time_match.group(0)
                    time_id = add_factor("time", time_form, span_id, role, polarity, time_form)
                else:
                    time_id = None

                noun_ids: List[str] = []
                for idx, ((token, _, _), (_, tag)) in enumerate(zip(offsets, tagged)):
                    if not (tag.startswith("NN") or tag in {"PRP", "PRP$"}):
                        continue
                    # Keep a compact candidate set: one factor per content noun.
                    if len(token) < 2 or token.lower() in {"thing", "something", "someone"}:
                        continue
                    ftype = "entity" if tag.startswith("NNP") or tag in {"PRP", "PRP$"} else "attribute"
                    candidate_id = add_factor(ftype, token, span_id, role, polarity, temporal)
                    if candidate_id:
                        noun_ids.append(candidate_id)
                    if len(noun_ids) >= 8:
                        break

                verb_indices = [idx for idx, (_, tag) in enumerate(tagged) if tag.startswith("VB") and tokens[idx].lower() not in SKIP_AUX]
                action_ids: List[str] = []
                for idx in verb_indices[:4]:
                    verb = tokens[idx]
                    candidate_id = add_factor("preference" if verb.lower() in PREFERENCE else "action", verb, span_id, role, polarity, temporal)
                    if candidate_id:
                        action_ids.append(candidate_id)

                for idx, predicate_id in zip(verb_indices[:4], action_ids):
                    left = next((fid for j, fid in enumerate(noun_ids) if j < len(noun_ids) and j < 3), None)
                    right = next((fid for j, fid in enumerate(noun_ids) if j >= 1), None)
                    if left and right and left != right:
                        rel_type = "prefers" if tokens[idx].lower() in PREFERENCE else "performs"
                        if len(relations) >= MAX_RELATIONS:
                            continue
                        relations.append({
                            "relation_id": f"re_{len(relations)+1:05d}",
                            "relation_type": rel_type,
                            "source_factor_ids": [left],
                            "target_factor_ids": [right],
                            "span_ids": [span_id],
                            "evidential_status": "explicit",
                            "causal_validation_required": False,
                        })
                    if predicate_id and time_id:
                        if len(relations) >= MAX_RELATIONS:
                            continue
                        relations.append({
                            "relation_id": f"re_{len(relations)+1:05d}",
                            "relation_type": "during",
                            "source_factor_ids": [predicate_id],
                            "target_factor_ids": [time_id],
                            "span_ids": [span_id],
                            "evidential_status": "explicit",
                            "causal_validation_required": False,
                        })

                for tool_id in [fid for fid in noun_ids if any(t in norm(f["normalized_form"]) for t in TOOL_WORDS for f in factors if f["factor_id"] == fid)]:
                    if action_ids:
                        if len(relations) >= MAX_RELATIONS:
                            continue
                        relations.append({
                            "relation_id": f"re_{len(relations)+1:05d}",
                            "relation_type": "uses_tool",
                            "source_factor_ids": [action_ids[0]],
                            "target_factor_ids": [tool_id],
                            "span_ids": [span_id],
                            "evidential_status": "explicit",
                            "causal_validation_required": False,
                        })

    # This lower-bound parser emits no abstract rules: syntactic co-occurrence
    # is insufficient evidence for a reusable rule or a causal claim.
    annotation = {
        "status": "in_progress",
        "annotator_id": "pos-regex-negative-control-v1",
        "evidence_spans": spans,
        "factors": factors,
        "relations": relations,
        "abstract_rule_candidates": [],
        "query_required_factor_ids": [],
        "counterexample_checks": [],
        "notes": "Query-independent POS/regex proxy; not semantic parsing or causal discovery.",
    }
    output = dict(packet)
    output["annotation"] = annotation
    output.pop("adjudication_only", None)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("packets", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0, help="Optional packet limit for smoke tests.")
    args = parser.parse_args()
    packets = [json.loads(line) for line in args.packets.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        packets = packets[: args.limit]
    # The default is a fully local deterministic POS proxy.  Passing a real
    # tagger is supported by the function for controlled comparisons, but is
    # intentionally not required for the auditable baseline artifact.
    predictions = [extract_packet(packet, None) for packet in packets]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for item in predictions), encoding="utf-8")
    print(json.dumps({"packets": len(predictions), "output_sha256": sha256_text(args.output.read_text(encoding="utf-8"))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
