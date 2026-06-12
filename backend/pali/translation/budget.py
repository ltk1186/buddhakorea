"""Pure budget guardrail helpers for Pali translation batch planning.

No provider APIs, database connections, or hardcoded official prices live here.
Callers inject price profiles and persisted budget state.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum
from typing import Any


USD_QUANT = Decimal("0.000001")


class BudgetDecisionReason(StrEnum):
    OK = "ok"
    KILL_SWITCH_ENABLED = "kill_switch_enabled"
    HARD_CAP_EXCEEDED = "hard_cap_exceeded"


@dataclass(frozen=True)
class PriceProfile:
    input_usd_per_million_tokens: Decimal
    output_usd_per_million_tokens: Decimal
    thinking_usd_per_million_tokens: Decimal = Decimal("0")
    batch_discount_multiplier: Decimal = Decimal("1")


@dataclass(frozen=True)
class TokenEstimate:
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0


@dataclass(frozen=True)
class BudgetState:
    actual_spent_usd: Decimal
    reserved_open_batches_usd: Decimal
    hard_cap_usd: Decimal
    kill_switch_enabled: bool = False


@dataclass(frozen=True)
class BudgetDecision:
    can_submit: bool
    reason: BudgetDecisionReason
    projected_total_usd: Decimal
    remaining_budget_usd: Decimal


@dataclass(frozen=True)
class UsageMetadata:
    prompt_token_count: int = 0
    candidates_token_count: int = 0
    thoughts_token_count: int = 0
    cached_content_token_count: int = 0
    total_token_count: int = 0


@dataclass(frozen=True)
class UsageParseResult:
    status: str
    usage: UsageMetadata | None
    error_message: str = ""


def estimate_request_cost(tokens: TokenEstimate, price_profile: PriceProfile) -> Decimal:
    input_cost = million_token_cost(
        tokens.input_tokens,
        price_profile.input_usd_per_million_tokens,
    )
    output_cost = million_token_cost(
        tokens.output_tokens,
        price_profile.output_usd_per_million_tokens,
    )
    thinking_cost = million_token_cost(
        tokens.thinking_tokens,
        price_profile.thinking_usd_per_million_tokens,
    )
    return quantize_usd(
        (input_cost + output_cost + thinking_cost)
        * price_profile.batch_discount_multiplier
    )


def estimate_batch_cost(
    token_estimates: list[TokenEstimate],
    price_profile: PriceProfile,
) -> Decimal:
    return quantize_usd(
        sum(
            (estimate_request_cost(tokens, price_profile) for tokens in token_estimates),
            Decimal("0"),
        )
    )


def can_submit_batch_under_budget(
    budget_state: BudgetState,
    new_batch_estimated_cost_usd: Decimal,
) -> BudgetDecision:
    projected = quantize_usd(
        budget_state.actual_spent_usd
        + budget_state.reserved_open_batches_usd
        + new_batch_estimated_cost_usd
    )
    remaining = quantize_usd(budget_state.hard_cap_usd - projected)
    if budget_state.kill_switch_enabled:
        return BudgetDecision(
            can_submit=False,
            reason=BudgetDecisionReason.KILL_SWITCH_ENABLED,
            projected_total_usd=projected,
            remaining_budget_usd=remaining,
        )
    if projected > budget_state.hard_cap_usd:
        return BudgetDecision(
            can_submit=False,
            reason=BudgetDecisionReason.HARD_CAP_EXCEEDED,
            projected_total_usd=projected,
            remaining_budget_usd=remaining,
        )
    return BudgetDecision(
        can_submit=True,
        reason=BudgetDecisionReason.OK,
        projected_total_usd=projected,
        remaining_budget_usd=remaining,
    )


def reserve_batch_budget(
    budget_state: BudgetState,
    estimated_cost_usd: Decimal,
) -> BudgetState:
    decision = can_submit_batch_under_budget(budget_state, estimated_cost_usd)
    if not decision.can_submit:
        raise ValueError(decision.reason.value)
    return replace(
        budget_state,
        reserved_open_batches_usd=quantize_usd(
            budget_state.reserved_open_batches_usd + estimated_cost_usd
        ),
    )


def reconcile_actual_usage(
    budget_state: BudgetState,
    *,
    reserved_cost_usd: Decimal,
    actual_cost_usd: Decimal,
) -> BudgetState:
    return replace(
        budget_state,
        reserved_open_batches_usd=max(
            Decimal("0"),
            quantize_usd(budget_state.reserved_open_batches_usd - reserved_cost_usd),
        ),
        actual_spent_usd=quantize_usd(budget_state.actual_spent_usd + actual_cost_usd),
    )


def is_kill_switch_enabled(budget_state: BudgetState) -> bool:
    return budget_state.kill_switch_enabled


def parse_usage_metadata(response: dict[str, Any]) -> UsageParseResult:
    usage_raw = response.get("usageMetadata") or response.get("usage_metadata")
    if not usage_raw:
        return UsageParseResult(
            status="needs_retry",
            usage=None,
            error_message="missing usage metadata",
        )
    usage = UsageMetadata(
        prompt_token_count=int(get_usage_value(usage_raw, "promptTokenCount", "prompt_token_count")),
        candidates_token_count=int(get_usage_value(usage_raw, "candidatesTokenCount", "candidates_token_count")),
        thoughts_token_count=int(get_usage_value(usage_raw, "thoughtsTokenCount", "thoughts_token_count")),
        cached_content_token_count=int(
            get_usage_value(usage_raw, "cachedContentTokenCount", "cached_content_token_count")
        ),
        total_token_count=int(get_usage_value(usage_raw, "totalTokenCount", "total_token_count")),
    )
    return UsageParseResult(status="success", usage=usage)


def actual_cost_from_usage(
    usage: UsageMetadata,
    price_profile: PriceProfile,
) -> Decimal:
    return estimate_request_cost(
        TokenEstimate(
            input_tokens=usage.prompt_token_count,
            output_tokens=usage.candidates_token_count,
            thinking_tokens=usage.thoughts_token_count,
        ),
        price_profile,
    )


def get_usage_value(data: dict[str, Any], camel_key: str, snake_key: str) -> int:
    value = data.get(camel_key, data.get(snake_key, 0))
    return int(value or 0)


def million_token_cost(tokens: int, usd_per_million: Decimal) -> Decimal:
    return (Decimal(tokens) / Decimal(1_000_000)) * usd_per_million


def quantize_usd(value: Decimal) -> Decimal:
    return value.quantize(USD_QUANT, rounding=ROUND_HALF_UP)
