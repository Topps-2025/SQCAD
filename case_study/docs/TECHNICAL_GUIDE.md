# SQCAD Case Study: The Decision a Score Cannot Make

## Purpose and evidence boundary

This artifact demonstrates lifecycle-aware authorization for persistent Agent Memory. Its central claim is deliberately narrower than a retrieval or ranking claim:

> Query relevance, current exposure quality, persistent lifecycle value, and authorization to keep are different estimands.

The replay is deterministic and illustrative. It is not a deployed system, a native reproduction of every named baseline, a benchmark leaderboard, or a SOTA claim. The browser does not call an LLM and does not read evaluator-only labels. The shared contract records `gold_sent_to_model: false`.

## The flagship case

The first replay is a score-fiber case. At the decision boundary the controller can observe the same:

- relevance score;
- recency and exposure history;
- co-exposure with successful answers;
- sparse lineage;
- scope and version metadata.

Two latent worlds are still possible. In one, a rare safety constraint becomes decisive and should be kept or probed. In the other, the memory is obsolete or mismatched and should be archived. A score-only controller must take the same action in both worlds, so it must be wrong in at least one continuation. The missing information is not simply a noisy score; it is information required to authorize a persistent action.

The interface makes this test explicit in two stages. First, the visitor must make only the two persistent commitments that a conventional controller would make: `keep` or `archive`. After the world tree is revealed, the page marks the commitment's regret in each latent world. Only then does the SQCAD path expose `resolve` and `probe` as evidence-seeking alternatives.

## State machine

```text
immutable source evidence
        |
        v
qualification: point / bound / unresolved / mismatch
        |
        +--> persistent authorization: keep / archive / isolate / defer
        |
        +--> current-task access: expose / defer / probe / temporary restore
                              |
                              v
                    adoption -> action -> outcome
                              |
                              v
                  later evidence remains observable
```

`temporary-restore` is not persistent `keep`. It is a scoped access decision for the current task. This separation prevents a useful one-off retrieval from silently changing the long-term memory policy. In the interactive tree, `resolve` means seeking lineage, scope, or a new source; `probe` means using the candidate reversibly while preserving its persistent authorization.

## Why exposure is causal

Persistent archive and downweight actions change future exposure. Less exposure produces less future evidence, which can make the memory appear even less useful:

```text
archive -> less exposure -> less evidence -> lower apparent value -> archive
```

The reverse hitchhiker failure is also possible: a useful memory and an irrelevant neighbor are exposed together, both receive success credit, and the neighbor is incorrectly authorized. SQCAD therefore treats adoption as evidence to qualify, not as permission by itself.

## Replay schema

`data/replay.json` uses `sqcad-case-study-replay.v2`.

| Field | Meaning |
|---|---|
| `signals` | Controller-visible signals at the decision boundary. |
| `branches` | Explanatory latent continuations revealed only after the visitor commits to a choice. |
| `events` | Deterministic current-time replay stream. |
| `qualification` | Evidence state: `point`, `bound`, `unresolved`, or `mismatch`. |
| `authorization` | Persistent lifecycle permission: `keep`, `archive`, `isolate`, `defer`, or `temporary`. |
| `access` | Current-task exposure state, including `guarded-candidate` and `temporary-restore`. |

The branch text is a teaching device, not an evaluator label fed to a controller. It is intentionally shown only after the interaction so the visitor can feel the score-fiber ambiguity.

## Method labels and claim discipline

- **SQCAD** is the proposed qualification-to-authorization path with defer and guarded probe actions.
- **Relevance only** is an association control that maps a surface proposal score to persistent keep.
- **Memory Worth** is a mechanism-faithful illustration of outcome co-occurrence as a trust signal; it is not presented as a native reproduction.
- **Oblivion decay** is a unified-contract adapter label for accessibility decay and reinforcement.
- **Trivium-RD** is a mechanism-faithful illustration of a budgeted probe.

Any future measured row must cite its frozen artifact and identify whether it is native, mechanism-faithful, proxy, or adapter evidence. Numbers currently displayed in the page are explanatory intervals, not experimental estimates.

## Godot companion

Godot is a companion renderer for the causal replay, not a replacement for the evidence inspector. The `godot/` scene draws source, archive, task exposure, and the two branch continuations. It can be exported for a Steam-style desktop build, while the browser remains the reviewable canonical surface. Keep the replay vocabulary synchronized with `data/replay.json`; do not introduce a second set of outcomes or hidden labels in the engine.

The important animation is branch divergence and reversible probe access. A room/world metaphor is intentionally avoided because it overlaps with Generative Agents-style demonstrations and distracts from the lifecycle decision.

## Anonymous deployment checklist

- Serve only `case_study/` and the public replay data.
- Do not expose `hidden.jsonl`, `results/`, `remote_results/`, local paths, notebook metadata, or credentials.
- Keep the evidence boundary footer visible.
- Keep generated images out of evidence diagrams and metric claims; exact labels remain HTML or code-rendered.

## Local verification

```powershell
python -m http.server 4173 --directory case_study
```

Check scenario switching, each decision choice, reveal gating, method switching, timeline stepping, desktop/mobile layout, and the absence of requests other than the local replay JSON and stylesheet/script assets.
