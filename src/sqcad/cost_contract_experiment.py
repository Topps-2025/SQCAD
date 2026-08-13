"""Gate 4: cost contract and net-benefit experiment.

The reviewer requires the baseline comparison to be about NET BENEFIT, not
raw utility:  V = sum_t gamma^(t-1) [ U_t - lam_tok*C_tok_t
  - lam_llm*C_llm_t - lam_probe*C_probe_t - lam_lat*C_lat_t
  - rho_harm*R_harm_t ] - rho_ff*R_ff

Every channel is computed from the unified runner's per-step decision rows
(same candidate stream, task sequence, workspace budget, evaluator, seeds
-- the Gate 1 contract), with the documented defaults:

  U_t       required-hit utility (the evaluator's only success signal)
  C_tok_t   workspace tokens (capacity cost; lam_tok = 0.001 matches the
            Gate 2 episodic value)
  C_llm_t   LLM endpoint cost -- 0 for every rule-based transport here
            (the LLM tiers were already labeled not reproduced in 05)
  C_probe_t qualification-time probes of unidentified item effects,
            charged at step 0 (the Gate 4 probe contract)
  C_lat_t   workspace size (wall-clock proxy: a larger workspace takes
            longer to read per step)
  R_harm_t  stale-exposure indicator (risk channel; rho_harm = 0.35
            matches the Gate 1 evaluator penalty)
  R_ff      episode-level low-frequency-protection charge: 4 - rare_kept
            (the cost of failing to protect rare critical memories)

Sections:
  E1  cost-contract table: V at the default and three regimes
      (risk-averse / capacity-constrained / latency-sensitive), with the
      component decomposition and an overall-efficiency ratio;
  E2  utility-risk-cost frontier: winner per regime, runner-ups;
  E3  explicit break-even: the probe price lambda_probe* at which the
      gated framework's net benefit equals the best baseline's, plus a
      rho_harm x lam_tok sweep locating the frontier flips;
  E4  negative lifecycle-restore result (KEPT on purpose): forced-decision
      controls -- blind_gate (decides persistent access from the raw point
      estimate where identification failed) and forced_restore ("when in
      doubt, keep": unidentified items are restored) -- are run on the
      standard world AND on a variant world where harmful (stale) items are
      themselves unidentified.  The controls collapse in value / in harm;
      the gated framework refuses and stays intact in both worlds.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import random
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .unified_agent_memory_runner import Candidate, Task, build_episode
from .unified_baseline_runner import (
    BASELINE_SPECS, run_policy_unified,
)

# ---------------------------------------------------------------------------
# Contract constants (frozen for the evidence run; the report registers them)
# ---------------------------------------------------------------------------

GAMMA = 0.99
LAM_TOK = 0.001      # token/capacity price (matches Gate 2 episodic value)
LAM_LLM = 0.0        # rule-based transports only: no LLM endpoint cost
LAM_PROBE = 0.05     # one qualification probe = 0.05 utility units
LAM_LAT = 0.002      # latency price per exposed item per step
RHO_HARM = 0.35      # stale-exposure risk price (matches Gate 1 penalty)
RHO_FF = 0.25        # low-frequency-protection fee per unprotected rare item

PROBE_BUDGET = 8     # shared contract probe budget (bound by the contract)

DEFAULT_COEF: Dict[str, float] = {
    "gamma": GAMMA, "lam_tok": LAM_TOK, "lam_llm": LAM_LLM,
    "lam_probe": LAM_PROBE, "lam_lat": LAM_LAT,
    "rho_harm": RHO_HARM, "rho_ff": RHO_FF,
}

REGIMES: Dict[str, Dict[str, float]] = {
    "default": dict(DEFAULT_COEF),
    "risk_averse": {**DEFAULT_COEF, "rho_harm": 1.0},
    "capacity": {**DEFAULT_COEF, "lam_tok": 0.01},
    "latency": {**DEFAULT_COEF, "lam_lat": 0.02},
}

# All transportable main-table rows plus the two forced-decision controls.
POLICIES = [p for p, s in BASELINE_SPECS.items()
            if s["transportability"] != "not_transportable"]
FORCED = ("blind_gate", "forced_restore")
ALL_POLICIES = POLICIES + list(FORCED)

# Variant world: harmful (stale) items become unidentified with this
# probability, so the identification gap contains BAD memories too.
UNIDENTIFIED_HARM_P = 0.75

# ---------------------------------------------------------------------------
# Cost contract arithmetic
# ---------------------------------------------------------------------------


def cost_components(rows: Sequence[Dict[str, float]], coef: Dict[str, float],
                    rare_kept_final: float) -> Dict[str, float]:
    """Discounted component decomposition of the cost contract."""
    gamma = coef["gamma"]
    utility = tokens = probes = latency = harm = 0.0
    disc = 1.0
    for r in rows:
        utility += disc * r["utility"]
        tokens += disc * r["tokens"]
        probes += disc * r["probes"]
        latency += disc * r["n_exposed"]
        harm += disc * r["stale"]
        disc *= gamma
    return {
        "utility": utility,
        "tokens": coef["lam_tok"] * tokens,
        "probes": coef["lam_probe"] * probes,
        "latency": coef["lam_lat"] * latency,
        "harm": coef["rho_harm"] * harm,
        "ff": coef["rho_ff"] * (4.0 - rare_kept_final),
        # informative raw sums (not charges)
        "n_probes": probes,
        "raw_latency_steps": latency,
    }


def cost_value(rows: Sequence[Dict[str, float]], coef: Dict[str, float],
               rare_kept_final: float) -> float:
    comps = cost_components(rows, coef, rare_kept_final)
    return (comps["utility"] - comps["tokens"] - comps["probes"]
            - comps["latency"] - comps["harm"] - comps["ff"])


def efficiency(rows: Sequence[Dict[str, float]]) -> float:
    """Overall efficiency: task utility per 1k workspace tokens
    (undiscounted ratio)."""
    util = sum(r["utility"] for r in rows)
    toks = sum(r["tokens"] for r in rows)
    return 1000.0 * util / toks if toks else 0.0


# ---------------------------------------------------------------------------
# Episode runners
# ---------------------------------------------------------------------------


def variant_episode(seed: int, group_noise: float, steps: int,
                    unidentified_harm_p: float = UNIDENTIFIED_HARM_P,
                    ) -> Tuple[List[Candidate], List[Task]]:
    """Standard episode post-processed so that a fraction of stale items
    carry an unidentified item effect (the identification gap contains
    harmful memories).  Deterministic per seed; identical stream for every
    policy in the variant block."""
    candidates, tasks = build_episode(seed, group_noise, steps)
    vrng = random.Random(seed * 104729 + 31)
    patched = [
        dataclasses.replace(c, item_effect_lcb=-1e6)
        if c.true_group == "stale" and vrng.random() < unidentified_harm_p
        else c
        for c in candidates
    ]
    return patched, tasks


def run_episode(seed: int, policy: str, probe_budget: int,
                use_variant_world: bool = False,
                group_noise: float = 0.2, steps: int = 100,
                budget: int = 12) -> Tuple[Dict[str, Any], List[Dict]]:
    rows: List[Dict] = []
    episode = variant_episode(seed, group_noise, steps) \
        if use_variant_world else None
    row = run_policy_unified(seed, policy, group_noise, steps, budget,
                             probe_budget=probe_budget, collect_rows=rows,
                             episode=episode)
    return row, rows


def episode_summary(row: Dict[str, Any], rows: List[Dict],
                    coef: Dict[str, float]) -> Dict[str, Any]:
    """One episode -> contract quantities (used by the aggregators)."""
    comps = cost_components(rows, coef, float(row["rare_kept_final"]))
    return {
        "V": cost_value(rows, coef, float(row["rare_kept_final"])),
        "utility": comps["utility"],
        "tokens": comps["tokens"],
        "probes": comps["probes"],
        "latency": comps["latency"],
        "harm": comps["harm"],
        "ff": comps["ff"],
        "n_probes": comps["n_probes"],
        "raw_latency_steps": comps["raw_latency_steps"],
        "utility_rate": float(row["required_evidence_recall"]),
        "rare_recall": float(row["rare_critical_recall"]),
        "stale_rate": float(row["stale_exposure_rate"]),
        "tokens_per_step": float(row["average_workspace_tokens"]),
        "rare_kept_final": float(row["rare_kept_final"]),
        "rare_kept_ever": float(row["rare_kept_ever"]),
        "efficiency": efficiency(rows),
        "stream_sha256": row["candidate_stream_sha256"],
    }


def aggregate(policies: Sequence[str], seeds: int, probe_budget: int,
              use_variant_world: bool = False,
              ) -> Dict[str, Dict[str, Any]]:
    """Mean over seeds of every contract quantity at every regime."""
    out: Dict[str, Dict[str, Any]] = {}
    per_seed: Dict[str, List[Dict]] = {p: [] for p in policies}
    for seed in range(seeds):
        stream_hash = None
        for policy in policies:
            row, rows = run_episode(seed, policy, probe_budget,
                                    use_variant_world=use_variant_world)
            if stream_hash is None:
                stream_hash = row["candidate_stream_sha256"]
            if row["candidate_stream_sha256"] != stream_hash:
                raise RuntimeError(
                    f"policies did not receive the same stream (seed {seed})")
            item = {"seed": seed}
            for name, coef in REGIMES.items():
                item[name] = episode_summary(row, rows, coef)
            per_seed[policy].append(item)
    for policy in policies:
        base = per_seed[policy][0]
        summed = {}
        for name in REGIMES:
            summed[name] = {
                k: mean(v[name][k] for v in per_seed[policy])
                for k in base[name]
                if isinstance(base[name][k], (int, float))}
        out[policy] = {
            "regimes": summed,
            "n_seeds": float(seeds),
        }
    return out


# ---------------------------------------------------------------------------
# E2 frontier / E3 break-even
# ---------------------------------------------------------------------------


def _transport_pool(table: Dict[str, Dict[str, Any]]) -> List[str]:
    """The frontier and the break-even compare TRANSPORTABLE governance
    strategies only; the forced-decision controls live in E4 (the negative
    lifecycle-restore result), where they are allowed to win the standard
    world and collapse in the variant world."""
    return [p for p in table if p not in FORCED]


def frontier(table: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Winner and runner-ups per regime over the transportable rows."""
    pool = _transport_pool(table)
    result: Dict[str, Any] = {}
    for regime in REGIMES:
        ranked = sorted(
            ((p, table[p]["regimes"][regime]["V"]) for p in pool),
            key=lambda kv: kv[1], reverse=True)
        result[regime] = {
            "winner": ranked[0][0],
            "winner_V": round(ranked[0][1], 3),
            "runner_up": ranked[1][0],
            "runner_up_V": round(ranked[1][1], 3),
            "ranked": [(p, round(v, 3)) for p, v in ranked],
        }
    return result


def break_even(table: Dict[str, Dict[str, Any]], framework: str,
               probe_budget: int) -> Dict[str, Any]:
    """lambda_probe* where V(framework) = V(best baseline).

    Only probe-bearing policies depend on lambda_probe: V(p, lam) =
    V(p, LAM_PROBE) + (LAM_PROBE - lam) * n_probes(p).  Report
      (a) the break-even against the best overall baseline (None when the
          framework's probe demand is not above the best baseline's: the
          lead does not vanish at any finite price), and
      (b) the price at which paying for qualification evidence stops being
          worthwhile against the best NON-probing baseline.
    """
    base = {p: table[p]["regimes"]["default"] for p in table}
    others = [p for p in table if p != framework and p not in FORCED]
    best = max(others, key=lambda p: base[p]["V"])
    non_probe = [p for p in others if base[p]["n_probes"] == 0.0]
    best_non_probe = (max(non_probe, key=lambda p: base[p]["V"])
                      if non_probe else None)

    v_fw, n_fw = base[framework]["V"], base[framework]["n_probes"]
    v_best, n_best = base[best]["V"], base[best]["n_probes"]

    lead_default = v_fw - v_best              # at the default probe price
    lead0 = lead_default + LAM_PROBE * (n_fw - n_best)  # at zero price

    if n_fw == n_best:
        if lead_default > 0:
            star, note = None, ("equal probe demand: the lead does not "
                                "depend on the probe price; no finite "
                                "price erases it")
        else:
            star, note = 0.0, ("framework at or below the best baseline "
                               "at default price")
    elif lead_default > 0 and n_fw < n_best:
        star, note = None, ("framework probes less than the best baseline: "
                            "the lead GROWS with the probe price")
    else:
        star = LAM_PROBE + lead_default / (n_best - n_fw)
        note = "explicit break-even at lambda_probe*"

    star_np = None
    if best_non_probe is not None:
        v_np = base[best_non_probe]["V"]
        lead0_np = v_fw - v_np + LAM_PROBE * n_fw
        if lead0_np <= 0:
            star_np = 0.0
        elif n_fw > 0:
            star_np = LAM_PROBE + (v_fw - v_np) / n_fw
    return {
        "framework": framework,
        "best_baseline": best,
        "best_baseline_V": round(v_best, 3),
        "lambda_probe_star": star,
        "best_non_probing_baseline": best_non_probe,
        "lambda_probe_star_vs_non_probing": star_np,
        "default_lambda_probe": LAM_PROBE,
        "headroom_multiplier": (star / LAM_PROBE) if star else None,
        "lead_V_at_zero_probe_price": round(lead0, 3),
        "lead_V_at_default_probe_price": round(lead_default, 3),
        "n_probes_framework": n_fw,
        "n_probes_best_baseline": n_best,
        "note": note,
    }


def sweep(table: Dict[str, Dict[str, Any]], top_k: Optional[int] = None,
          ) -> Dict[str, Any]:
    """rho_harm x lam_tok sweep over the transportable policies (the FULL
    pool: cutting to top-k by default V hides the no-memory control, which
    wins the capacity cells)."""
    pool = _transport_pool(table)
    ranked = sorted(pool,
                    key=lambda p: table[p]["regimes"]["default"]["V"],
                    reverse=True)
    if top_k is not None:
        ranked = ranked[:top_k]
    grid: Dict[str, Dict[str, Dict[str, float]]] = {}
    flips: List[Dict[str, Any]] = []
    for rho in (0.0, 0.35, 1.0):
        grid[str(rho)] = {}
        for lam in (0.001, 0.005, 0.01):
            coef = {**DEFAULT_COEF, "rho_harm": rho, "lam_tok": lam}
            values = {p: cost_from_regime(table, p, coef) for p in ranked}
            winner = max(values, key=values.get)
            if winner != "risk_gated_decomp_abstract":
                flips.append({"rho_harm": rho, "lam_tok": lam,
                              "winner": winner})
            grid[str(rho)][str(lam)] = values
    return {"policies": ranked, "grid": grid,
            "flips_from_framework": flips}


def probe_budget_sweep(seeds: int, probe_budgets: Sequence[int] = (0, 2, 4, 8),
                       ) -> Dict[str, Any]:
    """V of the probe-bearing strategies at DEFAULT prices under each probe
    budget, with the best non-probing transport as the constant reference.
    The framework's group fallback keeps rare protection at zero probe
    budget; CMI-style selection only catches up when the full budget is
    spent -- the structural margin shows under probe-budget stress."""
    policies = ("risk_gated_decomp_abstract", "causal_item", "trivium",
                "memory_worth", "rrf")
    out: Dict[str, Any] = {}
    for pb in probe_budgets:
        table = aggregate(policies, seeds, pb)
        default = {p: table[p]["regimes"]["default"] for p in policies}
        out[str(pb)] = {
            p: round(default[p]["V"], 3) for p in policies
        }
        out[str(pb)]["n_probes"] = {
            p: round(default[p]["n_probes"], 2) for p in policies}
        out[str(pb)]["winner"] = max(
            policies, key=lambda p: default[p]["V"])
    return out


def cost_from_regime(table: Dict[str, Dict[str, Any]], policy: str,
                     coef: Dict[str, float]) -> float:
    """V of one policy under an arbitrary coefficient set, recombined from
    the stored default-regime components (all channels are linear)."""
    comps = table[policy]["regimes"]["default"]
    # recompute charges with the new prices from the stored raw sums
    return (comps["utility"]
            - coef["lam_tok"] * comps["tokens"] / LAM_TOK
            - coef["lam_probe"] * comps["probes"] / LAM_PROBE
            - coef["lam_lat"] * comps["raw_latency_steps"]
            - coef["rho_harm"] * comps["harm"] / RHO_HARM
            - coef["rho_ff"] * comps["ff"] / RHO_FF)


# ---------------------------------------------------------------------------
# E4 negative lifecycle-restore result (KEPT)
# ---------------------------------------------------------------------------


def negative_result_block(table_std: Dict[str, Dict[str, Any]],
                          table_var: Dict[str, Dict[str, Any]],
                          ) -> Dict[str, Any]:
    def cells(table: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for p in FORCED + ("risk_gated_decomp_abstract", "causal_item",
                           "trivium"):
            reg = table[p]["regimes"]["default"]
            out[p] = {
                "V": round(reg["V"], 3),
                "utility_rate": round(reg["utility_rate"], 3),
                "rare_recall": round(reg["rare_recall"], 3),
                "stale_rate": round(reg["stale_rate"], 3),
                "n_probes": round(reg["n_probes"], 3),
                "tokens_per_step": round(reg["tokens_per_step"], 2),
            }
        return out

    std = cells(table_std)
    var = cells(table_var)
    return {
        "standard_world": std,
        "variant_world": var,
        "read": (
            "forced point-decision (blind_gate) converts the identification "
            "gap into a VALUE collapse (unidentified protective memories "
            "archived -> rare-required tasks fail); forced_restore converts "
            "it into a HARM collapse when harmful items are unidentified "
            "(stale restored into the workspace -> stale exposure every "
            "step).  The gated framework refuses the persistent decision "
            "where identification failed (probe or unresolved) and stays "
            "intact in both worlds.  This negative result is KEPT: the "
            "lifecycle-restore decision must not be forced."),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--budget", type=int, default=12)
    parser.add_argument("--group-noise", type=float, default=0.2)
    parser.add_argument("--probe-budget", type=int, default=PROBE_BUDGET)
    parser.add_argument("--output", type=Path,
                        default=Path("results/cost_contract.json"))
    parser.add_argument("--fast", action="store_true",
                        help="small config for CI/tests")
    args = parser.parse_args()

    seeds = 3 if args.fast else args.seeds
    probe_budget = 4 if args.fast else args.probe_budget

    table_std = aggregate(POLICIES + list(FORCED), seeds, probe_budget)
    table_var = aggregate(("risk_gated_decomp_abstract", "causal_item",
                           "trivium") + FORCED, seeds, probe_budget,
                          use_variant_world=True)

    result = {
        "protocol": {
            "purpose": "Gate 4 cost contract: net benefit, frontier, "
                       "break-even, negative lifecycle-restore result",
            "contract": ("V = sum_t gamma^(t-1)[U_t - lam_tok*C_tok_t "
                         "- lam_llm*C_llm_t - lam_probe*C_probe_t "
                         "- lam_lat*C_lat_t - rho_harm*R_harm_t] "
                         "- rho_ff*R_ff"),
            "coefficients_default": DEFAULT_COEF,
            "regimes": REGIMES,
            "probe_budget": probe_budget,
            "unidentified_harm_p": UNIDENTIFIED_HARM_P,
            "seeds": seeds, "steps_per_seed": args.steps,
            "workspace_item_budget": args.budget,
            "group_noise": args.group_noise,
            "shared": "same candidate stream, task sequence, workspace "
                      "budget, evaluator and seeds (Gate 1 contract); "
                      "forced controls are NOT rows of the main table",
            "lam_llm_note": "C_llm = 0: every transported rule is a "
                            "deterministic function of the shared stream; "
                            "the LLM tiers were labeled not reproduced in "
                            "the Gate 1 table",
        },
        "E1_cost_contract": {
            p: {
                "regimes": {name: {k: round(v, 4)
                                   for k, v in reg.items()}
                            for name, reg in table_std[p]["regimes"].items()},
                "n_seeds": table_std[p]["n_seeds"],
            }
            for p in table_std},
        "E2_frontier": frontier(table_std),
        "E3_break_even": break_even(
            table_std, "risk_gated_decomp_abstract", probe_budget),
        "E3_sweep": sweep(table_std),
        "E3_probe_budget_sweep": probe_budget_sweep(seeds),
        "E4_negative_lifecycle_restore": negative_result_block(
            table_std, table_var),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(json.dumps({
        "E1_default_V": {p: table_std[p]["regimes"]["default"]["V"]
                         for p in table_std},
        "E2_winner_per_regime": {r: result["E2_frontier"][r]["winner"]
                                 for r in REGIMES},
        "E3_break_even": result["E3_break_even"],
        "E4_standard": result["E4_negative_lifecycle_restore"]
                       ["standard_world"],
        "E4_variant": result["E4_negative_lifecycle_restore"]["variant_world"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
