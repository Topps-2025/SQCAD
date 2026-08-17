# Method

## Problem formulation

At task time $t$, the system receives a target scope $s_t$ containing task, user, tool, model/version, risk and policy metadata. A shared candidate proposer returns candidates $C_t$ and inexpensive association scores $r_{i,t}$. Each candidate has immutable evidence records and a scoped qualification state:

$$Q(i, s) \in \{\text{positive},\ \text{negative},\ \text{unresolved},\ \text{mismatch}\}.$$

Only qualified evidence may modify persistent access policy. Access remains reversible and source evidence is never deleted.

## Candidate guard

Relevance candidates are proposed broadly (BM25 is the static coverage upper bound and cost control, not a governance method). To repair evidence coverage without relaxing persistent-write authorization, at most $k$ top proposed candidates enter the current read pool in addition to qualified candidates. Guard-1 ($k=1$, chronologically restricted, one-shot exposure) is the minimal fix evaluated on public data; Guard-2/4 trade more coverage for more probe/restore cost. The guard never changes the persistent qualification state by itself.

## Permission layer

The qualification layer reads provenance, evidence type, support, scope/version overlap, drift and audit status. Positive and negative decisions are scope-specific. Unresolved evidence cannot produce a persistent positive or negative update; it may receive bounded fallback access when query match is strong and risk is low.

Round-verified rules (2026-08-17, LifecycleBench matrix):

- **lineage conflict → archive** (was conservative keep): a version conflict marks the old fact as untrustworthy; conservative keep caused catastrophic false commits (−119.53 on `version_update/update_before` vs −0.54 with the conflict rule, = oracle upper bound; global paired bootstrap +8.62 significant).
- **hitchhiker association-only → archive**: a memory with no independent signal (only co-exposure) must not default to keep; probe_willing (archive unless POSITIVE) is the global best non-oracle policy (+0.865). The mechanism-level trade-off (qualification threshold vs probe cost) is refined in Phase B.
- **future scope (scope lookahead) → deferred**: needing more than "a future task exists in another scope" (whether the future task *requires* the decision memory) — first Phase B validation point.

The qualification interface must expose its evidence, threshold, calibration, audit status and rollback path. An LLM explanation alone is not causal evidence.

## Access layer

For a candidate $i$ in scope $s$ and task $t$, a pre-registered access logit can be written as:

$$z(i,s,t) = r(i,t) + \alpha\,\mathrm{positive}(i,s) - \beta\,\mathrm{negative}(i,s) - \gamma\,\mathrm{scope\_mismatch}(i,s) - \eta\,\mathrm{cost}(i)$$

The logits are projected to a fixed workspace budget $B_t$, for example by a temperature-controlled normalized allocation:

$$a(i,s,t) = B_t \cdot \frac{\exp(z(i,s,t)/T)}{\sum_j \exp(z(j,s,t)/T)}$$

The implementation may use a discrete top-k or sparse projection, but the main experiment freezes one implementation before testing. Increasing access mass for qualified evidence automatically reduces the relative mass available to other candidates; focus and decay are two views of the same budget projection.

## Lifecycle and audit

The online path records candidate generation, exposure, position, adoption, action, outcome and cost. Ordinary outcomes update association only. Qualification updates occur asynchronously through auditable evidence, randomized low-risk interventions or human review. Scope shifts, version changes and conflicts trigger revalidation. Evidence, belief and access are stored separately so that an incorrect access decision can be reversed without erasing the source.

## Decision layer

A persistent commit requires provable qualification. With identification bounds $(L, U)$ from the qualification layer, the decision rule compares three options under one cost contract:

$$\min\{R^*(L,U),\ C_{\text{defer}},\ C_{\text{probe}} + R^*_{\text{after\_probe}}\}$$

where $R^*(L,U) = \frac{U(-L)}{U-L}$ is the minimax regret of committing. The identification set must not cross the action boundary; otherwise the action stays unresolved, defers, or pays for a probe/restore that reopens the evidence channel. Archive-induced silence is censoring, not negative evidence: evidence starvation caused by a past action must be distinguishable from true non-value before any further decay.

## Complexity and boundary

The shared retriever, writer, reader, LLM and evaluator are infrastructure rather than claimed novelty. SQCAD does not claim causal discovery from observational success, universal transport across scopes, permanent global retention or physical deletion.
