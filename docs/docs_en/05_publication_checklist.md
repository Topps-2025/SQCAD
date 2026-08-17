# Publication checklist

**Done:**

- [x] Freeze repository commit, Python version and dependency lock.
- [x] Run the full deterministic test suite from a clean environment (CPU-only, no keys).
- [x] Verify external database manifest and dataset hashes (four-piece freeze chain).
- [x] Build and hash-verify the self-built benchmark (LifecycleBench, 1,380 episodes; remote rebuild identical).
- [x] Run R1–R5, R7 fairness defenses with preregistered verdicts (truth checkable, failures possible, generalization challengeable, evaluation not guessable).
- [x] Relocate fragile-parameter results (R2) to the valid domain instead of deleting them.
- [x] Reproduce the public pipeline on a remote GPU and close the cloud session.
- [x] Separate local reproduction, paper-reported numbers, proxy and oracle results.

**Open:**

- [ ] Complete R6 human anchoring (28 blinded cases; Cohen's κ ≥ 0.6) and archive judge packets.
- [ ] Run Phase B end-to-end (frozen reader/LLM/tools; only persistent state switches) — first validation of scope lookahead.
- [ ] Reproduce named governance baselines under the unified contract (agent vs official columns); report `not reproduced` where unavailable.
- [ ] Release the R7 public package (anonymized `public_trace_only.jsonl` + official scorer) and verify licenses before redistribution.
- [ ] Add only claims supported by the claim–evidence map (see report 21, claim boundaries).

**Claim discipline:**

- Can claim: separating candidate proposal, qualification and access; archive/restore/probe as identification-constrained actions; Guard-1 as a minimal coverage fix; LifecycleBench as directly scorable keep/archive long-term value.
- Must disclose: reference certificate is a full proxy of the visible-event rule in the rule world; R2 sensitive parameter region; R6 and Phase B not completed.
- Cannot claim: causal benefit proven in real deployment; systematic superiority over all SOTA; relevance as qualification evidence; public QA F1 as direct evidence of long-term lifecycle value.
