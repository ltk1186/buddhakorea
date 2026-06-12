from decimal import Decimal

import pytest

from backend.pali.translation.batch_plan import (
    BatchSegmentPlan,
    build_provider_jsonl_line,
    parse_batch_result_line,
    split_segments_into_budgeted_shards,
)
from backend.pali.translation.budget import (
    BudgetDecisionReason,
    BudgetState,
    PriceProfile,
    TokenEstimate,
    actual_cost_from_usage,
    can_submit_batch_under_budget,
    estimate_request_cost,
    parse_usage_metadata,
    reconcile_actual_usage,
    reserve_batch_budget,
)


def price_profile() -> PriceProfile:
    return PriceProfile(
        input_usd_per_million_tokens=Decimal("10"),
        output_usd_per_million_tokens=Decimal("20"),
        thinking_usd_per_million_tokens=Decimal("30"),
        batch_discount_multiplier=Decimal("0.5"),
    )


def segment(key: str, input_tokens: int = 100_000, output_tokens: int = 100_000) -> BatchSegmentPlan:
    return BatchSegmentPlan(
        stable_segment_key=key,
        source_text_hash=f"hash-{key}",
        source_path="romn/s0505m.mul.xml",
        text_layer="mula",
        chunk_type="prose",
        prompt_text=f"Translate {key}",
        estimated_input_tokens=input_tokens,
        estimated_output_tokens=output_tokens,
    )


def test_cost_estimate_uses_injected_price_profile_and_thinking_tokens():
    cost = estimate_request_cost(
        TokenEstimate(input_tokens=100_000, output_tokens=50_000, thinking_tokens=10_000),
        price_profile(),
    )
    assert cost == Decimal("1.150000")


def test_hard_cap_blocks_submit_with_reserved_budget():
    state = BudgetState(
        actual_spent_usd=Decimal("90"),
        reserved_open_batches_usd=Decimal("9"),
        hard_cap_usd=Decimal("100"),
    )
    decision = can_submit_batch_under_budget(state, Decimal("2"))
    assert decision.can_submit is False
    assert decision.reason == BudgetDecisionReason.HARD_CAP_EXCEEDED


def test_kill_switch_blocks_submit():
    state = BudgetState(
        actual_spent_usd=Decimal("0"),
        reserved_open_batches_usd=Decimal("0"),
        hard_cap_usd=Decimal("100"),
        kill_switch_enabled=True,
    )
    decision = can_submit_batch_under_budget(state, Decimal("1"))
    assert decision.can_submit is False
    assert decision.reason == BudgetDecisionReason.KILL_SWITCH_ENABLED


def test_reserve_and_reconcile_actual_usage():
    state = BudgetState(
        actual_spent_usd=Decimal("10"),
        reserved_open_batches_usd=Decimal("0"),
        hard_cap_usd=Decimal("100"),
    )
    reserved = reserve_batch_budget(state, Decimal("5"))
    assert reserved.reserved_open_batches_usd == Decimal("5.000000")

    reconciled = reconcile_actual_usage(
        reserved,
        reserved_cost_usd=Decimal("5"),
        actual_cost_usd=Decimal("4.25"),
    )
    assert reconciled.reserved_open_batches_usd == Decimal("0.000000")
    assert reconciled.actual_spent_usd == Decimal("14.250000")


def test_split_segments_into_budgeted_shards_respects_limits():
    shards = split_segments_into_budgeted_shards(
        [segment("a"), segment("b"), segment("c")],
        price_profile=price_profile(),
        max_estimated_cost_usd=Decimal("2"),
        max_segments=2,
    )
    assert len(shards) == 3
    assert all(len(shard.segments) == 1 for shard in shards)


def test_provider_jsonl_line_uses_stable_key():
    line = build_provider_jsonl_line(
        segment("seg-1"),
        generation_config={"temperature": 0.2, "response_mime_type": "application/json"},
    )
    assert line["key"] == "seg-1"
    assert line["request"]["contents"][0]["parts"][0]["text"] == "Translate seg-1"


def test_parse_usage_metadata_and_actual_cost():
    parsed = parse_usage_metadata(
        {
            "usageMetadata": {
                "promptTokenCount": 100,
                "candidatesTokenCount": 50,
                "thoughtsTokenCount": 10,
                "cachedContentTokenCount": 20,
                "totalTokenCount": 160,
            }
        }
    )
    assert parsed.status == "success"
    assert parsed.usage is not None
    assert parsed.usage.thoughts_token_count == 10
    assert actual_cost_from_usage(parsed.usage, price_profile()) == Decimal("0.001150")


def test_missing_usage_metadata_needs_retry():
    parsed = parse_usage_metadata({"text": "{}"})
    assert parsed.status == "needs_retry"
    assert parsed.usage is None


def test_parse_batch_result_line_distinguishes_error_and_success():
    failed = parse_batch_result_line({"key": "seg-1", "error": {"code": 500}})
    assert failed.status == "failed"
    assert failed.stable_segment_key == "seg-1"

    success = parse_batch_result_line(
        {
            "key": "seg-2",
            "response": {
                "candidates": [{"content": {"parts": [{"text": "{}"}]}}],
                "usageMetadata": {
                    "promptTokenCount": 1,
                    "candidatesTokenCount": 1,
                    "totalTokenCount": 2,
                },
            },
        }
    )
    assert success.status == "succeeded"
    assert success.usage_status == "success"

    needs_retry = parse_batch_result_line({"key": "seg-3", "response": {"candidates": []}})
    assert needs_retry.status == "needs_retry"
