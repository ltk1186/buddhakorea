from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from backend.pali.scripts.run_pilot_1000_dry_run import main as dry_run_main
from backend.pali.translation.natural_ko_readability import NATURAL_KO_V2_2_MARKER
from backend.pali.translation.natural_ko_calibration_smoke import compare_v2_2_d_arm
from backend.pali.translation.pilot_1000_dry_run import (
    PINNED_INVENTORY_COMMIT,
    build_request_preview,
    build_validation_report,
    corpus_extrapolation,
    estimate_costs,
    read_jsonl,
    run_pilot_1000_dry_run,
    step6_paths,
    validate_preview,
)


def make_manifest_and_inventory(tmp_path: Path, count: int = 1000) -> tuple[Path, Path, dict, dict]:
    items = []
    inventory_items = []
    layers = ["mula", "atthakatha", "tika"]
    lengths = ["short", "medium", "long"]
    chunks = ["prose", "verse"]
    for index in range(count):
        layer = layers[index % len(layers)]
        length = lengths[(index // len(layers)) % len(lengths)]
        chunk = chunks[(index // (len(layers) * len(lengths))) % len(chunks)]
        source_path = f"romn/{'abh' if index % 5 == 0 else 's'}{index:04d}.mul.xml"
        key = f"vri:romn:test{index:04d}:{index:012x}"
        source_hash = f"hash-{index:04d}"
        manifest_item = {
            "stable_segment_key": key,
            "source_path": source_path,
            "source_text_hash": source_hash,
            "text_layer": layer,
            "chunk_type": chunk,
            "length_bucket": length,
            "selection_group": "representative" if index < 700 else "hard",
            "selection_bucket": "fixture",
            "source_commit": PINNED_INVENTORY_COMMIT,
        }
        items.append(manifest_item)
        inventory_items.append(
            {
                **manifest_item,
                "original_text": f"Evaṃ me sutaṃ {index}. Dhammo ca vinayo ca.",
                "normalized_text": f"Evaṃ me sutaṃ {index}. Dhammo ca vinayo ca.",
                "canonical_ref": f"fixture:{index}",
                "heading_path": [],
            }
        )
    manifest = {
        "schema_version": "pali_pilot_1000_selection_v1",
        "inventory_source_commit": PINNED_INVENTORY_COMMIT,
        "pilot_1000_new_count": count,
        "response_schema_default_for_1000": True,
        "salvage_cascade_fallback": True,
        "items": items,
    }
    inventory = {
        "schema_version": "fixture_inventory",
        "source_commit": PINNED_INVENTORY_COMMIT,
        "items": inventory_items,
    }
    manifest_path = tmp_path / "pilot_1000_v1_manifest.json"
    inventory_path = tmp_path / "inventory.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    inventory_path.write_text(json.dumps(inventory, ensure_ascii=False), encoding="utf-8")
    return manifest_path, inventory_path, manifest, inventory


def test_dry_run_generates_1000_request_preview_and_preserves_metadata(tmp_path: Path) -> None:
    manifest_path, inventory_path, manifest, _inventory = make_manifest_and_inventory(tmp_path)
    out = tmp_path / "out"
    result = run_pilot_1000_dry_run(
        manifest_path=manifest_path,
        inventory_cache_path=inventory_path,
        out_dir=out,
        response_schema=True,
        dry_run=True,
        hard_cap_usd=Decimal("1000"),
        pretty=True,
    )
    paths = step6_paths(out)
    rows = read_jsonl(paths.request_preview)
    assert result["status"] == "PASS"
    assert len(rows) == 1000
    assert len({row["key"] for row in rows}) == 1000
    assert [row["key"] for row in rows] == [item["stable_segment_key"] for item in manifest["items"]]
    first = rows[0]
    assert first["metadata"]["source_text_hash"] == manifest["items"][0]["source_text_hash"]
    assert first["metadata"]["source_path"] == manifest["items"][0]["source_path"]
    assert first["metadata"]["original_text"]


def test_response_schema_generation_config_and_prompt_invariants(tmp_path: Path) -> None:
    manifest_path, inventory_path, _manifest, _inventory = make_manifest_and_inventory(tmp_path)
    run_pilot_1000_dry_run(
        manifest_path=manifest_path,
        inventory_cache_path=inventory_path,
        out_dir=tmp_path / "out",
        response_schema=True,
        dry_run=True,
        hard_cap_usd=Decimal("1000"),
    )
    rows = read_jsonl(step6_paths(tmp_path / "out").request_preview)
    configs = [json.dumps(row["request"]["generation_config"], sort_keys=True, ensure_ascii=False) for row in rows]
    assert len(set(configs)) == 1
    config = rows[0]["request"]["generation_config"]
    schema = config["response_schema"]
    prompt = rows[0]["request"]["contents"][0]["parts"][0]["text"]
    assert config["temperature"] == 0.2
    assert config["response_mime_type"] == "application/json"
    assert "propertyOrdering" in schema
    assert "additionalProperties" not in json.dumps(schema)
    assert set(schema["properties"]) == {
        "literal_ko",
        "natural_ko",
        "terms",
        "grammar_notes",
        "doctrinal_notes",
        "uncertainties",
        "quality_flags",
    }
    assert "reader_ko" not in prompt
    assert "reader_ko" not in json.dumps(schema)
    assert NATURAL_KO_V2_2_MARKER in prompt
    assert "빠알리 문장 구조와 어순을 가능한 한 보존하십시오" not in prompt
    assert "한국어가 다소 어색해도 괜찮습니다" not in prompt


def test_cost_estimate_cap_and_validation_block_when_over_cap(tmp_path: Path) -> None:
    manifest_path, inventory_path, _manifest, inventory = make_manifest_and_inventory(tmp_path)
    result = run_pilot_1000_dry_run(
        manifest_path=manifest_path,
        inventory_cache_path=inventory_path,
        out_dir=tmp_path / "out",
        response_schema=True,
        dry_run=True,
        hard_cap_usd=Decimal("0.01"),
    )
    assert result["status"] == "BLOCKED"
    cost = json.loads(step6_paths(tmp_path / "out").cost_estimate_json.read_text(encoding="utf-8"))
    validation = json.loads(step6_paths(tmp_path / "out").validation_report_json.read_text(encoding="utf-8"))
    assert cost["bucket_estimates"]
    assert cost["pilot_1000_total_cost_mean"]
    assert cost["pilot_1000_total_cost_p90"]
    assert cost["cap_passed"] is False
    assert validation["submit_ready"] is False
    assert "BLOCKED_ESTIMATED_P90_COST_OVER_CAP" in validation["errors"]
    rows = read_jsonl(step6_paths(tmp_path / "out").request_preview)
    preview_validation = validate_preview(json.loads(manifest_path.read_text()), inventory["items"], rows)
    pass_cost = estimate_costs(rows, Decimal("1000"))
    assert build_validation_report(preview_validation, pass_cost)["cap_passed"] is True


def test_corpus_extrapolation_uses_joint_counts_and_marginal_fallback(tmp_path: Path) -> None:
    manifest_path, inventory_path, _manifest, inventory = make_manifest_and_inventory(tmp_path)
    run_pilot_1000_dry_run(
        manifest_path=manifest_path,
        inventory_cache_path=inventory_path,
        out_dir=tmp_path / "out",
        response_schema=True,
        dry_run=True,
        hard_cap_usd=Decimal("1000"),
    )
    cost = json.loads(step6_paths(tmp_path / "out").cost_estimate_json.read_text(encoding="utf-8"))
    joint = corpus_extrapolation(cost, inventory)
    marginal = corpus_extrapolation(cost, {"items": []})
    assert joint["corpus_weighting_method"] == "joint_inventory_counts"
    assert joint["full_corpus_segment_count"] == 1000
    assert marginal["corpus_weighting_method"] == "marginal_independence_approximation"
    assert marginal["full_corpus_segment_count"] == 203594
    assert "Do not multiply pilot average cost" in marginal["warning"]


def test_manifest_and_plans_record_local_only_invariants(tmp_path: Path) -> None:
    manifest_path, inventory_path, _manifest, _inventory = make_manifest_and_inventory(tmp_path)
    out = tmp_path / "out"
    run_pilot_1000_dry_run(
        manifest_path=manifest_path,
        inventory_cache_path=inventory_path,
        out_dir=out,
        response_schema=True,
        dry_run=True,
        hard_cap_usd=Decimal("1000"),
    )
    paths = step6_paths(out)
    manifest = json.loads(paths.dry_run_manifest_json.read_text(encoding="utf-8"))
    submit_plan = paths.submit_plan_md.read_text(encoding="utf-8")
    qa_plan = paths.qa_retry_plan_md.read_text(encoding="utf-8")
    assert manifest["api_llm_calls"] == 0
    assert manifest["network_calls"] == 0
    assert manifest["batch_submissions"] == 0
    assert manifest["live_submit_started"] is False
    assert manifest["selection_reused_not_reselected"] is True
    assert manifest["planned_requests"] == 1000
    assert "This is documentation only" in submit_plan
    assert "FAIL_RETRY_ONLY" in qa_plan
    assert "FAIL_BLOCKING" in qa_plan


def test_cli_blocks_submit_flag_without_live_path(tmp_path: Path, capsys) -> None:
    code = dry_run_main(["--submit", "--out", str(tmp_path)])
    captured = capsys.readouterr()
    assert code == 2
    assert "BLOCKED_LIVE_MODE_UNSUPPORTED" in captured.err


def test_existing_mixed_bracket_and_insertion_is_fail_blocking() -> None:
    item = {
        "stable_segment_key": "vri:romn:abh02m.mul:a8d464d40a45",
        "original_text": "kammārāmatā",
        "literal_ko": "[그것은] 직역이다.",
        "natural_ko": "세속적인 일을 즐김이다.",
        "terms": [{"pali": "kammārāmatā", "ko": "일을 즐김"}],
        "schema_valid": True,
        "parse_method": "strict_json",
    }
    items = [item] + [
        {
            "stable_segment_key": f"ok-{index}",
            "original_text": "dhamma",
            "literal_ko": "직역이다.",
            "natural_ko": "자연역이다.",
            "terms": [],
            "schema_valid": True,
            "parse_method": "strict_json",
        }
        for index in range(29)
    ]
    comparison = compare_v2_2_d_arm({"items": items}, None, None, None)
    assert comparison["objective_gate_status"] == "FAIL_BLOCKING"
    assert comparison["blocking_failures"]
    assert comparison["retry_only_failures"]
