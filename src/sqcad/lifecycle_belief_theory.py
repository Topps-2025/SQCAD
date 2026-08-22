"""Finite diagnostics for the Agent lifecycle belief-control theorems.

These functions audit theorem witnesses; they are not substitutes for the
measure-theoretic proofs in docs/自用/01-research-gap/研究逻辑与理论证明/19-*.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass
from math import exp, isfinite, log, log1p


@dataclass(frozen=True)
class LifecycleContrast:
    immediate: float
    access: float
    information: float
    gamma: float

    @property
    def total(self) -> float:
        return self.immediate + self.gamma * (self.access + self.information)


@dataclass(frozen=True)
class RecoverabilityValue:
    continuation: float
    access: float
    conditional_information: float


def _validate_probability_distribution(
    distribution: Mapping[Hashable, float],
    *,
    atol: float,
) -> None:
    if not distribution:
        raise ValueError("transcript distributions must not be empty")
    if any(not isfinite(probability) for probability in distribution.values()):
        raise ValueError("transcript probabilities must be finite")
    if any(probability < -atol for probability in distribution.values()):
        raise ValueError("transcript probabilities must be non-negative")
    if abs(sum(distribution.values()) - 1.0) > atol:
        raise ValueError("transcript probabilities must sum to one")


def finite_lifecycle_trichotomy(
    states: Sequence[Hashable],
    tasks: Sequence[Hashable],
    scores: Mapping[Hashable, Hashable],
    keep_transcripts: Mapping[
        tuple[Hashable, Hashable], Mapping[Hashable, float]
    ],
    archive_transcripts: Mapping[
        tuple[Hashable, Hashable], Mapping[Hashable, float]
    ],
    *,
    immediate_contrasts: Mapping[tuple[Hashable, Hashable], float] | None = None,
    atol: float = 1e-12,
) -> str:
    """Classify a finite intervention-defined memory channel.

    The return value is one of ``future-null``, ``lifecycle-complete``, or
    ``future-lossy``. When immediate contrasts are supplied, this function
    also enforces the theorem's score-visible-current-cost premise.
    """
    if atol < 0.0:
        raise ValueError("atol must be non-negative")
    if not states or not tasks:
        raise ValueError("states and tasks must not be empty")

    signed_kernels: dict[
        tuple[Hashable, Hashable], dict[Hashable, float]
    ] = {}
    non_null = False
    for task in tasks:
        for state in states:
            key = (state, task)
            keep = keep_transcripts[key]
            archive = archive_transcripts[key]
            _validate_probability_distribution(keep, atol=atol)
            _validate_probability_distribution(archive, atol=atol)
            support = set(keep) | set(archive)
            signed = {
                outcome: keep.get(outcome, 0.0) - archive.get(outcome, 0.0)
                for outcome in support
            }
            signed_kernels[key] = signed
            non_null = non_null or any(abs(value) > atol for value in signed.values())

    fibers: dict[Hashable, list[Hashable]] = defaultdict(list)
    for state in states:
        fibers[scores[state]].append(state)

    if immediate_contrasts is not None:
        for task in tasks:
            for fiber in fibers.values():
                reference = immediate_contrasts[(fiber[0], task)]
                if not isfinite(reference):
                    raise ValueError("immediate contrasts must be finite")
                for state in fiber[1:]:
                    value = immediate_contrasts[(state, task)]
                    if not isfinite(value):
                        raise ValueError("immediate contrasts must be finite")
                    if abs(value - reference) > atol:
                        raise ValueError(
                            "immediate contrasts must be constant on score fibers"
                        )

    if not non_null:
        return "future-null"

    for task in tasks:
        for fiber in fibers.values():
            reference = signed_kernels[(fiber[0], task)]
            for state in fiber[1:]:
                candidate = signed_kernels[(state, task)]
                support = set(reference) | set(candidate)
                if any(
                    abs(reference.get(outcome, 0.0) - candidate.get(outcome, 0.0))
                    > atol
                    for outcome in support
                ):
                    return "future-lossy"
    return "lifecycle-complete"


def task_universal_shifted_regret(
    first_lifecycle_value: float,
    second_lifecycle_value: float,
) -> dict[str, float]:
    """Return the midpoint shift and exact two-state minimax regret.

    This audits the cost-uniform witness in the trichotomy. It does not claim
    that the original fixed-cost contrasts already select opposite actions.
    """
    if not isfinite(first_lifecycle_value) or not isfinite(second_lifecycle_value):
        raise ValueError("lifecycle values must be finite")
    if first_lifecycle_value == second_lifecycle_value:
        raise ValueError("lifecycle values must differ")
    midpoint_shift = 0.5 * (first_lifecycle_value + second_lifecycle_value)
    first_shifted = first_lifecycle_value - midpoint_shift
    second_shifted = second_lifecycle_value - midpoint_shift
    return {
        "midpoint_shift": midpoint_shift,
        "first_shifted_contrast": first_shifted,
        "second_shifted_contrast": second_shifted,
        "minimax_regret": abs(first_lifecycle_value - second_lifecycle_value) / 4.0,
    }


def lifecycle_contrast(
    immediate_keep: float,
    immediate_archive: float,
    access_keep: float,
    access_archive: float,
    information_keep: float,
    information_archive: float,
    gamma: float,
) -> LifecycleContrast:
    """Return the three terms in Theorem A's keep/archive contrast."""
    if not 0.0 <= gamma <= 1.0:
        raise ValueError("gamma must lie in [0, 1]")
    return LifecycleContrast(
        immediate=immediate_keep - immediate_archive,
        access=access_keep - access_archive,
        information=information_keep - information_archive,
        gamma=gamma,
    )


def recoverability_value(
    access_keep: float,
    access_archive: float,
    information_keep: float,
    information_archive: float,
    gamma: float,
) -> RecoverabilityValue:
    """Separate general continuation VoR from conditional information VoR."""
    if not 0.0 <= gamma <= 1.0:
        raise ValueError("gamma must lie in [0, 1]")
    access = gamma * (access_keep - access_archive)
    conditional_information = gamma * (information_keep - information_archive)
    return RecoverabilityValue(
        continuation=access + conditional_information,
        access=access,
        conditional_information=conditional_information,
    )


def finite_score_quotient_violations(
    states: Sequence[Hashable],
    actions: Sequence[Hashable],
    quotient: Mapping[Hashable, Hashable],
    rewards: Mapping[tuple[Hashable, Hashable], float],
    transitions: Mapping[tuple[Hashable, Hashable], Mapping[Hashable, float]],
    *,
    atol: float = 1e-12,
) -> list[str]:
    """Audit finite-state reward factorization and controlled lumpability."""
    if atol < 0.0:
        raise ValueError("atol must be non-negative")
    fibers: dict[Hashable, list[Hashable]] = defaultdict(list)
    for state in states:
        fibers[quotient[state]].append(state)

    violations: list[str] = []
    for action in actions:
        aggregated: dict[Hashable, dict[Hashable, float]] = {}
        for state in states:
            distribution = transitions[(state, action)]
            total = sum(distribution.values())
            if any(probability < -atol for probability in distribution.values()):
                raise ValueError("transition probabilities must be non-negative")
            if abs(total - 1.0) > atol:
                raise ValueError("transition probabilities must sum to one")
            by_quotient: dict[Hashable, float] = defaultdict(float)
            for next_state, probability in distribution.items():
                by_quotient[quotient[next_state]] += probability
            aggregated[state] = dict(by_quotient)

        for fiber_states in fibers.values():
            reference = fiber_states[0]
            for state in fiber_states[1:]:
                if abs(rewards[(reference, action)] - rewards[(state, action)]) > atol:
                    violations.append(
                        f"reward:{action!r}:{reference!r}!={state!r}"
                    )
                quotient_states = set(aggregated[reference]) | set(aggregated[state])
                if any(
                    abs(aggregated[reference].get(z, 0.0) - aggregated[state].get(z, 0.0))
                    > atol
                    for z in quotient_states
                ):
                    violations.append(
                        f"transition:{action!r}:{reference!r}!={state!r}"
                    )
    return violations


def value_separating_signed_kernel_contrasts(
    future_gap_first: float,
    future_gap_second: float,
    gamma: float,
) -> dict[str, float]:
    """Construct opposite contrasts from two value-separated kernel gaps.

    The two inputs are integrals of one admissible continuation value against
    the signed keep--archive kernels. Kernel inequality alone is insufficient
    unless the task class can realize a value that separates the kernels.
    """
    if gamma <= 0.0 or gamma > 1.0:
        raise ValueError("gamma must lie in (0, 1]")
    if future_gap_first == future_gap_second:
        raise ValueError("future gaps must differ")
    immediate = -0.5 * gamma * (future_gap_first + future_gap_second)
    return {
        "immediate_contrast": immediate,
        "first_contrast": immediate + gamma * future_gap_first,
        "second_contrast": immediate + gamma * future_gap_second,
    }


def two_state_score_regret(delta_positive: float, delta_negative: float) -> dict[str, float]:
    """Minimax and least-favorable Bayes regret on one score fiber.

    ``delta_positive`` is the keep/archive gap in the keep-optimal state;
    ``delta_negative`` is the negative gap in the archive-optimal state.
    """
    if delta_positive <= 0.0 or delta_negative >= 0.0:
        raise ValueError("the two lifecycle contrasts must have opposite signs")
    d1 = delta_positive
    d2 = -delta_negative
    p_keep = d1 / (d1 + d2)
    regret = d1 * d2 / (d1 + d2)
    return {
        "p_keep_minimax": p_keep,
        "minimax_regret": regret,
        "least_favorable_mass_positive": d2 / (d1 + d2),
        "least_favorable_mass_negative": d1 / (d1 + d2),
        "least_favorable_bayes_regret": regret,
    }


def fiber_minimax_regret(lower: float, upper: float) -> dict[str, float]:
    """Minimax score-only regret for a closed lifecycle-contrast fiber."""
    if lower > upper:
        raise ValueError("lower must not exceed upper")
    if lower >= 0.0:
        return {"p_keep": 1.0, "regret": 0.0, "quarter_width_bound": (upper - lower) / 4.0}
    if upper <= 0.0:
        return {"p_keep": 0.0, "regret": 0.0, "quarter_width_bound": (upper - lower) / 4.0}

    width = upper - lower
    p_keep = upper / width
    regret = upper * (-lower) / width
    return {
        "p_keep": p_keep,
        "regret": regret,
        "quarter_width_bound": width / 4.0,
    }


def binary_classification_information_value(
    signal_accuracy: float,
    reward: float = 1.0,
) -> float:
    """Information value for a symmetric binary world and optimal decision.

    With prior 1/2, an uninformative experiment has value ``reward / 2``.
    A symmetric signal with accuracy in [1/2, 1] has value
    ``reward * signal_accuracy`` after observing the signal.
    """
    if not 0.5 <= signal_accuracy <= 1.0:
        raise ValueError("signal_accuracy must lie in [0.5, 1]")
    if reward < 0.0:
        raise ValueError("reward must be non-negative")
    return reward * (signal_accuracy - 0.5)


def probe_is_bayes_preferred(expected_information_value: float, cost: float, gamma: float) -> bool:
    """The strict probe/defer threshold from Corollary D.2."""
    if expected_information_value < 0.0 or cost < 0.0:
        raise ValueError("information value and cost must be non-negative")
    if not 0.0 <= gamma <= 1.0:
        raise ValueError("gamma must lie in [0, 1]")
    return gamma * expected_information_value > cost


def recoverability_regret_lower_bound(
    positive_gap: float,
    negative_gap: float,
    transcript_kl: float,
) -> float:
    """Bretagnolle-Huber lifecycle-regret floor for two Agent worlds.

    ``positive_gap`` is the keep advantage in the keep-optimal world and
    ``negative_gap`` is the archive advantage in the archive-optimal world.
    ``transcript_kl`` is the KL divergence between the complete adaptive
    transcripts available when persistent authorization is issued.
    """
    if positive_gap <= 0.0 or negative_gap <= 0.0:
        raise ValueError("both lifecycle action gaps must be positive")
    if transcript_kl < 0.0:
        raise ValueError("transcript_kl must be non-negative")
    harmonic_gap = positive_gap * negative_gap / (positive_gap + negative_gap)
    return 0.5 * harmonic_gap * exp(-transcript_kl)


def required_recoverability_kl(
    positive_gap: float,
    negative_gap: float,
    target_regret: float,
) -> float:
    """Necessary transcript KL for the theorem's regret floor to be at most target."""
    if target_regret <= 0.0:
        raise ValueError("target_regret must be positive")
    zero_information_floor = recoverability_regret_lower_bound(
        positive_gap,
        negative_gap,
        transcript_kl=0.0,
    )
    if target_regret >= zero_information_floor:
        return 0.0
    return log(zero_information_floor / target_regret)


def priced_recoverability_regret_floor(
    positive_gap: float,
    negative_gap: float,
    kl_per_action: float,
    action_cost: float,
) -> float:
    """Worst-world loss floor when reopening the evidence channel is priced.

    Each channel-opening action costs at least ``action_cost`` and contributes
    at most ``kl_per_action`` nats. The result is the minimum over the expected
    action count of the larger of diagnostic cost and terminal authorization
    regret. It equals ``action_cost / kl_per_action * W(kl_per_action *
    alpha / action_cost)``, where ``alpha`` is the zero-information two-world
    regret floor and ``W`` is the principal Lambert-W branch.
    """
    if positive_gap <= 0.0 or negative_gap <= 0.0:
        raise ValueError("both lifecycle action gaps must be positive")
    if kl_per_action < 0.0:
        raise ValueError("kl_per_action must be non-negative")
    if action_cost <= 0.0:
        raise ValueError("action_cost must be positive")
    if not all(
        isfinite(value)
        for value in (positive_gap, negative_gap, kl_per_action, action_cost)
    ):
        raise ValueError("inputs must be finite")

    alpha = recoverability_regret_lower_bound(
        positive_gap,
        negative_gap,
        transcript_kl=0.0,
    )
    if kl_per_action == 0.0:
        return alpha

    z = kl_per_action * alpha / action_cost
    if not isfinite(z):
        raise ValueError("combined scale must be finite")
    upper = max(1.0, log1p(z))
    lower = 0.0
    for _ in range(80):
        midpoint = 0.5 * (lower + upper)
        if midpoint * exp(midpoint) < z:
            lower = midpoint
        else:
            upper = midpoint
    lambert_w = 0.5 * (lower + upper)
    return action_cost * lambert_w / kl_per_action
