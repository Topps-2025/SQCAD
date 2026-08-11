# Candidate v4 controlled challenge experiment

> This report tests the unverified v4 hypotheses only. It does not replace the formal v3 evidence and is not a public benchmark.

## Protocol

- 240 shared stochastic worlds; 6 policies; same candidate streams and probe potential outcomes.
- Policies: keep-all, fixed decay, v3 qualification gate, point-estimate scope gate, full Bayesian scope–transport gate, and a warm-start challenge variant.
- World factors: scoped value, version drift, confounded association, observable transport similarity, asymmetric task risk.
- The evaluator observes latent value only to score outcomes; policies do not read it.
- Bayesian probes are capped at twelve per world and execute only when a fixed EVSI proxy exceeds the pre-registered price.

## Aggregate results

| Policy | Utility | FF regret ↓ | Harmful retention ↓ | Active tokens ↓ | Probe cost | Brier ↓ |
|---|---:|---:|---:|---:|---:|---:|
| keep_all | -1.623 ± 0.350 | 0.000 ± 0.000 | 8.164 ± 0.186 | 28.000 ± 0.000 | 0.000 | n/a |
| fixed_decay | 4.432 ± 0.223 | 2.075 ± 0.082 | 1.796 ± 0.070 | 14.031 ± 0.221 | 0.000 | n/a |
| v3_gate | 4.530 ± 0.228 | 1.912 ± 0.068 | 1.841 ± 0.069 | 14.366 ± 0.204 | 0.000 | n/a |
| point_scope | 3.053 ± 0.158 | 5.396 ± 0.132 | 0.419 ± 0.026 | 5.751 ± 0.174 | 0.000 | n/a |
| bayes_full | 0.926 ± 0.084 | 7.125 ± 0.151 | 0.229 ± 0.015 | 3.059 ± 0.088 | 0.720 | 0.247 |
| bayes_warm | 1.179 ± 0.090 | 6.574 ± 0.159 | 0.438 ± 0.024 | 4.436 ± 0.085 | 0.720 | 0.247 |

## Contrasts against the current v3 gate

Positive utility is better; lower FF regret, harmful retention and active tokens are better.

| Candidate | Δ utility | Δ FF regret | Δ harmful retention | Δ active tokens | Δ active fraction | Δ Brier |
|---|---:|---:|---:|---:|---:|---:|
| keep_all | -6.153 | -1.912 | +6.323 | +13.634 | +0.4869 | n/a |
| fixed_decay | -0.097 | +0.163 | -0.045 | -0.335 | -0.0120 | n/a |
| point_scope | -1.476 | +3.484 | -1.422 | -8.615 | -0.3077 | n/a |
| bayes_full | -3.604 | +5.214 | -1.612 | -11.307 | -0.4038 | n/a |
| bayes_warm | -3.351 | +4.662 | -1.403 | -9.930 | -0.3547 | n/a |

## Pre-registered Go/No-Go reading

1. **Scope gate:** compare `bayes_full` with `point_scope`; a gain would support posterior uncertainty and transport gating beyond a point estimate.
2. **Asymmetric access:** inspect harmful-retention versus FF-regret jointly; a one-sided gain is not sufficient for a broad performance claim.
3. **Less-is-more:** active-token reduction is required at matched future utility; token reduction alone is not a success criterion.
4. **Calibration:** lower Brier is supportive but not a substitute for randomized micro-intervention calibration.

## Boundary and next experiment

This controlled world deliberately isolates mechanism behavior. It cannot establish public-benchmark transfer, real-agent adoption observability, evaluator stability or causal identification. Any positive v4 result therefore supports retaining the hypothesis for a preregistered future-split and randomized micro-intervention study; any failed gate requires deleting or simplifying the corresponding module.

Reproduce with:
```powershell
python v4_scope_bayesian_experiment.py
```
