# LifecycleBench-v3

A benchmark for **persistent memory authorization**: given only decision-time
context, should a memory item stay persistently authorized (`keep`) or be moved
out of the active workspace (`archive`)?

Unlike retrieval benchmarks, the label is not "is this relevant to the next
question". It is the sign of a **paired counterfactual continuation value**:
the same world is rolled out twice, once under `keep` and once under `archive`,
and the oracle action is whichever branch scores higher under the declared cost
contract. That makes score-fiber failures measurable — two states can share a
relevance score and still have opposite correct commitments.

## Contents

| File | Rows | What it is |
|---|---:|---|
| `worlds.jsonl` | 225 | World identity: entity alias, mechanism family, seed, `world_signature` |
| `public.jsonl` | 225 | **Decision-time input.** Memories, scopes, versions, visible sessions, the decision task |
| `hidden.jsonl` | 225 | **Evaluator-side truth.** `needed_future_ids`, `rescue_possible`, `scope_validity`, oracle action |
| `policy_rows.jsonl` | 225 | Frozen paired rollout branches used to score value and regret |
| `baseline_summary.json` | — | Frozen reference scores: 14 deterministic policies, ablations, per-family breakdown |
| `manifest.json` | — | Version, world count, signature uniqueness, source contract path |

`world_signature_unique_rate` is 1.000: all 225 worlds are distinct, so the
**inferential unit is the world signature**, and the 9 mechanism families are
the bootstrap clusters.

## The one rule that matters

**Never read `hidden.jsonl` in a controller.** A controller consumes
`public.jsonl` only. Hidden fields exist so an evaluator can score you; using
them is not a strong result, it is a leak. The reference harnesses record
`gold_sent_to_model: false` for exactly this reason.

## Quickstart

```python
import json

public = [json.loads(l) for l in open("public.jsonl",  encoding="utf-8")]
hidden = [json.loads(l) for l in open("hidden.jsonl",  encoding="utf-8")]

row = public[0]
row["decision_memory"]          # fid under decision
row["decision_task"]["query"]   # the visible task
row["memories"]                 # candidates: fid, text, scope, version, storage_tokens
```

Run the bundled baselines and score them — no dependencies beyond the standard
library, no GPU, no API key:

```bash
python example_controller.py --rule qualify_lineage --out actions.json
python score.py --actions actions.json --by-family
```

A submission is just `episode_id -> "keep" | "archive"`, as a flat JSON mapping
or as JSONL records with `episode_id` and `action`. All 225 worlds must be
present: the inferential unit is the world signature, so dropping worlds changes
the estimand and `score.py` refuses to score a partial file.

Rebuild the dataset from source (deterministic; reproduces the same signatures):

```bash
PYTHONPATH=src python tools/build_lifecycle_bench_v3.py --out results/lifecycle_bench_v3
```

## Metrics

- **value / regret** — discounted net utility of the committed branch, and the
  gap to the oracle branch.
- **false commit** — kept when archive was correct. **missed commit** — archived
  when keep was correct.
- **recoverability at budget** — `keep` counts as available; `archive` counts
  only when the frozen branch says rescue was possible.
- **scope/version correctness** — scored on the `scope_mismatch` and
  `version_update` families only, where the notion is defined.
- **authorized vs physical storage** — reported separately. Archiving reduces
  authorization, not bytes on disk.

## Reference points

From `baseline_summary.json` (225 worlds, deterministic policies):

| Policy | Value | Regret | False commit | Missed commit |
|---|---:|---:|---:|---:|
| `oracle_policy` | 1.987 | 0.040 | 0.000 | 0.000 |
| `sqcad_cert_conflict` | 1.083 | 0.944 | 0.196 | 0.000 |
| `memory_worth` | -1.052 | 3.079 | 0.147 | 0.071 |
| `simplemem_lexical` | -7.753 | 9.780 | 0.298 | 0.000 |
| `keep_all` | -9.184 | 11.211 | 0.427 | 0.000 |
| `frequency2` | -10.892 | 12.919 | 0.409 | 0.151 |

`keep_all` scoring worse than `archive_all` is the point of the benchmark:
retaining everything is expensive and wrong, and relevance-ranked retention
(`simplemem_lexical`, `frequency2`) does not fix it.

The bundled `example_controller.py` reproduces this from the public layer alone:

| Rule | Value | Regret | False commit | Missed commit | Scope/ver. |
|---|---:|---:|---:|---:|---:|
| `relevance` | -7.747 | 9.774 | 0.298 | 0.000 | 0.380 |
| `qualify` | -7.189 | 9.216 | 0.267 | 0.000 | 0.380 |
| `qualify_lineage` | +1.706 | 0.321 | 0.018 | 0.098 | 0.800 |

`qualify` matches the frozen `sqcad_cert` row exactly, which is a useful check
that your environment reproduces the contract. The jump to `qualify_lineage`
comes from one added test — is this item superseded by a live counterpart —
and that single mechanism is what separates the SQCAD rows from relevance
ranking. It buys a lower false-commit rate at the cost of some missed commits,
which is the trade-off the paper's certificate band is meant to manage.

`ablation_summary` in the same file shows that only **censoring suppression** is
activated by this generator: removing it moves regret from 9.216 to 11.123,
while `no_lineage`, `no_probe`, `no_qualification`, and `no_restore` all leave
the score unchanged. Note that this block ablates the `sqcad_cert` variant
(regret 9.216), not the conflict-aware `sqcad_cert_conflict` row above. A
separately synchronized run that ablates `sqcad_cert_conflict` reports the same
direction from the 0.944 base (regret 11.021, value -8.994); it is the figure
quoted in the paper.

The zero-effect entries are honest negative evidence about identifiability under
this world family, not a claim those mechanisms are unnecessary in general.

## Scope and limits

Program-generated worlds with a declared cost contract. Results measure
control behavior **under that generator** — they are not evidence about
real-agent traces, and the paper does not claim otherwise. The lexicalization
is templated, so absolute answer quality is not meaningful here; the
counterfactual sign structure is.

## License

MIT, same as the repository. See `../../LICENSE`.
