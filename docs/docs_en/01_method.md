# Method

## Problem formulation

At task time `t`, the system receives a target scope `s_t` containing task, user, tool, model/version, risk and policy metadata. A shared candidate proposer returns candidates `C_t` and inexpensive association scores `r_i,t`. Each candidate has immutable evidence records and a scoped qualification state:

`Q(i, s) ∈ {positive, negative, unresolved, mismatch}`.

Only qualified evidence may modify persistent access policy. Access remains reversible and source evidence is never deleted.

## Permission layer

The qualification layer reads provenance, evidence type, support, scope/version overlap, drift and audit status. Positive and negative decisions are scope-specific. Unresolved evidence cannot produce a persistent positive or negative update; it may receive bounded fallback access when query match is strong and risk is low.

The qualification interface must expose its evidence, threshold, calibration, audit status and rollback path. An LLM explanation alone is not causal evidence.

## Access layer

For a candidate `i` in scope `s` and task `t`, a pre-registered access logit can be written as:

```text
z(i,s,t) = r(i,t) + α·positive(i,s) − β·negative(i,s)
           − γ·scope_mismatch(i,s) − η·cost(i)
```

The logits are projected to a fixed workspace budget `B_t`, for example by a temperature-controlled normalized allocation:

```text
a(i,s,t) = B_t · exp(z(i,s,t)/T) / Σ_j exp(z(j,s,t)/T)
```

The implementation may use a discrete top-k or sparse projection, but the main experiment freezes one implementation before testing. Increasing access mass for qualified evidence automatically reduces the relative mass available to other candidates; focus and decay are two views of the same budget projection.

## Lifecycle and audit

The online path records candidate generation, exposure, position, adoption, action, outcome and cost. Ordinary outcomes update association only. Qualification updates occur asynchronously through auditable evidence, randomized low-risk interventions or human review. Scope shifts, version changes and conflicts trigger revalidation. Evidence, belief and access are stored separately so that an incorrect access decision can be reversed without erasing the source.

## Decision layer

A persistent commit requires provable qualification. With identification bounds `(L, U)` from the qualification layer, the decision rule compares three options under one cost contract:

```text
min{ R*(L,U),  C_defer,  C_probe + R*_after_probe }
```

where `R*(L,U) = U(−L)/(U−L)` is the minimax regret of committing. The identification set must not cross the action boundary; otherwise the action stays unresolved, defers, or pays for a probe/restore that reopens the evidence channel. Archive-induced silence is censoring, not negative evidence: evidence starvation caused by a past action must be distinguishable from true non-value before any further decay.

## Complexity and boundary

The shared retriever, writer, reader, LLM and evaluator are infrastructure rather than claimed novelty. SQCAD does not claim causal discovery from observational success, universal transport across scopes, permanent global retention or physical deletion.
