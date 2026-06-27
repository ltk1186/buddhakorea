from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from backend.pali.scripts.submit_pilot_1000_batch import main as live_main
from backend.pali.translation.natural_ko_readability import NATURAL_KO_V2_2_MARKER
from backend.pali.translation.pilot_1000_live import (
    PINNED_INVENTORY_COMMIT,
    PLANNED_REQUESTS,
    build_retry_bracket_plan,
    classify_item_gate,
    content_preservation_guard,
    fetch_live_results,
    parse_live_results,
    preflight_submit,
    report_outputs,
    run_qa,
    step7_paths,
    submit_live_batch,
    poll_live_batch,
)
from backend.pali.translation.natural_ko_v2_2_quality import evaluate_d_arm_item
from backend.pali.translation.response_schema_smoke import build_response_schema_experiment


def output_payload(**overrides):
    payload = {
        "literal_ko": "직역이다.",
        "natural_ko": "자연역이다.",
        "terms": [],
        "grammar_notes": [],
        "doctrinal_notes": [],
        "uncertainties": [],
        "quality_flags": [],
    }
    payload.update(overrides)
    return payload


def result_line(key: str, text: str | None = None, *, error: dict | None = None) -> dict:
    if error:
        return {"metadata": {"key": key}, "error": error}
    return {
        "metadata": {"key": key},
        "response": {
            "candidates": [{"content": {"parts": [{"text": text or json.dumps(output_payload(), ensure_ascii=False)}]}}],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
                "thoughtsTokenCount": 3,
                "totalTokenCount": 18,
            },
        },
    }


def make_preview_row(index: int, *, prompt_extra: str = "", schema: dict | None = None, metadata_extra: dict | None = None) -> dict:
    key = f"vri:romn:test{index:04d}:{index:012x}"
    metadata = {
        "stable_segment_key": key,
        "source_path": f"romn/test{index:04d}.xml",
        "source_text_hash": f"hash-{index:04d}",
        "text_layer": ["mula", "atthakatha", "tika"][index % 3],
        "chunk_type": "verse" if index % 5 == 0 else "prose",
        "length_bucket": ["short", "medium", "long"][index % 3],
        "original_text": f"dhamma {index}",
    }
    if metadata_extra:
        metadata.update(metadata_extra)
    prompt = f"{NATURAL_KO_V2_2_MARKER}\n충실하다는 것은 빠알리 어순을 그대로 따라가는 것이 아닙니다.\n빠알리 원문: <<<{metadata['original_text']}>>>\n{prompt_extra}"
    return {
        "key": key,
        "arm": "pilot_1000",
        "metadata": metadata,
        "request": {
            "model": "models/gemini-3.1-pro-preview",
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generation_config": {
                "temperature": 0.2,
                "response_mime_type": "application/json",
                "response_schema": schema or build_response_schema_experiment()["response_schema"],
            },
        },
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def make_live_fixture(tmp_path: Path, *, count: int = PLANNED_REQUESTS) -> tuple[Path, Path, Path, list[dict]]:
    out = tmp_path / "out"
    preview_path = tmp_path / "preview.jsonl"
    manifest_path = tmp_path / "manifest.json"
    rows = [make_preview_row(index) for index in range(count)]
    items = [
        {
            "stable_segment_key": row["key"],
            "source_path": row["metadata"]["source_path"],
            "source_text_hash": row["metadata"]["source_text_hash"],
            "text_layer": row["metadata"]["text_layer"],
            "chunk_type": row["metadata"]["chunk_type"],
            "length_bucket": row["metadata"]["length_bucket"],
        }
        for row in rows
    ]
    manifest = {
        "schema_version": "pali_pilot_1000_selection_v1",
        "inventory_source_commit": PINNED_INVENTORY_COMMIT,
        "items": items,
    }
    step6_manifest = {
        "step": "6-pilot-1000-dry-run",
        "inventory_source_commit": PINNED_INVENTORY_COMMIT,
        "planned_requests": count,
        "submit_ready": True,
        "cap_passed": True,
        "estimated_cost_usd_mean": "27.626031",
        "estimated_cost_usd_p90": "32.109922",
        "hard_cap_usd": "50.000000",
    }
    step6_validation = {
        "schema_version": "pali_pilot_1000_validation_v1",
        "dry_run_status": "PASS",
        "planned_requests": count,
        "submit_ready": True,
        "cap_passed": True,
        "estimated_cost_usd_p90": "32.109922",
        "hard_cap_usd": "50.000000",
    }
    write_jsonl(preview_path, rows)
    write_json(manifest_path, manifest)
    paths = step7_paths(out)
    write_json(paths.step6_manifest, step6_manifest)
    write_json(paths.step6_validation, step6_validation)
    return out, preview_path, manifest_path, rows


def run_preflight_fixture(tmp_path: Path) -> tuple[dict, Path, Path, Path, list[dict]]:
    out, preview, manifest, rows = make_live_fixture(tmp_path)
    result = preflight_submit(request_preview_path=preview, manifest_path=manifest, out_dir=out, hard_cap_usd=Decimal("50"))
    return result, out, preview, manifest, rows


def test_preflight_passes_with_valid_synthetic_files(tmp_path: Path) -> None:
    result, _out, _preview, _manifest, _rows = run_preflight_fixture(tmp_path)
    assert result["status"] == "PASS"
    assert result["planned_requests"] == 1000
    assert result["request_preview_sha256"]
    assert result["api_llm_calls"] == 0
    assert result["network_calls"] == 0


def test_preflight_blocks_bad_preview_count_duplicates_schema_reader_and_cap(tmp_path: Path) -> None:
    out, preview, manifest, rows = make_live_fixture(tmp_path)
    write_jsonl(preview, rows[:-1])
    assert preflight_submit(request_preview_path=preview, manifest_path=manifest, out_dir=out)["status"] == "BLOCKED"

    out, preview, manifest, rows = make_live_fixture(tmp_path / "dup")
    rows[1]["key"] = rows[0]["key"]
    write_jsonl(preview, rows)
    assert preflight_submit(request_preview_path=preview, manifest_path=manifest, out_dir=out)["status"] == "BLOCKED"

    out, preview, manifest, rows = make_live_fixture(tmp_path / "schema")
    del rows[0]["request"]["generation_config"]["response_schema"]
    write_jsonl(preview, rows)
    assert preflight_submit(request_preview_path=preview, manifest_path=manifest, out_dir=out)["status"] == "BLOCKED"

    out, preview, manifest, rows = make_live_fixture(tmp_path / "additional")
    rows[0]["request"]["generation_config"]["response_schema"]["additionalProperties"] = False
    write_jsonl(preview, rows)
    assert preflight_submit(request_preview_path=preview, manifest_path=manifest, out_dir=out)["status"] == "BLOCKED"

    out, preview, manifest, rows = make_live_fixture(tmp_path / "ordering")
    rows[0]["request"]["generation_config"]["response_schema"].pop("propertyOrdering")
    write_jsonl(preview, rows)
    assert preflight_submit(request_preview_path=preview, manifest_path=manifest, out_dir=out)["status"] == "BLOCKED"

    out, preview, manifest, rows = make_live_fixture(tmp_path / "reader")
    rows[0]["request"]["contents"][0]["parts"][0]["text"] += "\nreader_ko"
    write_jsonl(preview, rows)
    assert preflight_submit(request_preview_path=preview, manifest_path=manifest, out_dir=out)["status"] == "BLOCKED"

    out, preview, manifest, rows = make_live_fixture(tmp_path / "old")
    rows[0]["request"]["contents"][0]["parts"][0]["text"] += "\n빠알리 문장 구조와 어순을 가능한 한 보존하십시오"
    write_jsonl(preview, rows)
    assert preflight_submit(request_preview_path=preview, manifest_path=manifest, out_dir=out)["status"] == "BLOCKED"

    out, preview, manifest, _rows = make_live_fixture(tmp_path / "cap")
    paths = step7_paths(out)
    step6 = json.loads(paths.step6_manifest.read_text(encoding="utf-8"))
    step6["cap_passed"] = False
    write_json(paths.step6_manifest, step6)
    assert preflight_submit(request_preview_path=preview, manifest_path=manifest, out_dir=out)["status"] == "BLOCKED"


class MockClient:
    def __init__(self) -> None:
        self.created = []
        self.status = {"name": "batches/mock-1", "state": "BATCH_STATE_SUCCEEDED", "inlinedResponses": []}

    def create_inline_batch(self, *, model: str, requests: list[dict], display_name: str) -> dict:
        self.created.append({"model": model, "requests": requests, "display_name": display_name})
        return {"name": "batches/mock-1", "state": "BATCH_STATE_PENDING"}

    def get_batch(self, name: str) -> dict:
        assert name == "batches/mock-1"
        return self.status


def test_submit_guards_hash_and_duplicate_then_records_mock_batch(tmp_path: Path) -> None:
    result, out, preview, manifest, rows = run_preflight_fixture(tmp_path)
    paths = step7_paths(out)
    rows[0]["metadata"]["original_text"] = "changed"
    write_jsonl(preview, rows)
    try:
        submit_live_batch(request_preview_path=preview, manifest_path=manifest, out_dir=out, client=MockClient())
    except Exception as exc:
        assert "hash" in str(exc).lower()
    else:
        raise AssertionError("submit should block on changed hash")

    write_jsonl(preview, [make_preview_row(index) for index in range(PLANNED_REQUESTS)])
    preflight_submit(request_preview_path=preview, manifest_path=manifest, out_dir=out)
    submit = submit_live_batch(request_preview_path=preview, manifest_path=manifest, out_dir=out, client=MockClient())
    assert submit["provider_batch_id"] == "batches/mock-1"
    assert json.loads(paths.submit_run_manifest.read_text(encoding="utf-8"))["provider_batch_id"] == "batches/mock-1"
    try:
        submit_live_batch(request_preview_path=preview, manifest_path=manifest, out_dir=out, client=MockClient())
    except Exception as exc:
        assert "duplicate" in str(exc).lower() or "already" in str(exc).lower()
    else:
        raise AssertionError("duplicate submit should block")


def test_poll_fetch_use_mock_client_without_autochaining(tmp_path: Path) -> None:
    _result, out, preview, manifest, _rows = run_preflight_fixture(tmp_path)
    client = MockClient()
    submit_live_batch(request_preview_path=preview, manifest_path=manifest, out_dir=out, client=client)
    client.status = {"name": "batches/mock-1", "state": "BATCH_STATE_SUCCEEDED", "inlinedResponses": [result_line("vri:romn:test0000:000000000000")]}
    polled = poll_live_batch(out_dir=out, client=client)
    assert polled["status"] == "POLLED"
    fetched = fetch_live_results(out_dir=out, client=client)
    assert fetched["raw_result_count"] == 1


def test_parse_strict_and_preserves_metadata_excluding_raw_payload(tmp_path: Path) -> None:
    _result, out, preview, manifest, rows = run_preflight_fixture(tmp_path)
    paths = step7_paths(out)
    write_jsonl(paths.raw_results, [result_line(row["key"]) for row in rows])
    parsed = parse_live_results(request_preview_path=preview, manifest_path=manifest, out_dir=out)
    payload = json.loads(paths.parsed.read_text(encoding="utf-8"))
    first = payload["items"][0]
    assert parsed["strict_json_count"] == 1000
    assert first["stable_segment_key"] == rows[0]["key"]
    assert first["source_text_hash"] == rows[0]["metadata"]["source_text_hash"]
    assert first["source_path"] == rows[0]["metadata"]["source_path"]
    assert first["original_text"] == rows[0]["metadata"]["original_text"]
    assert "model_output_raw" not in first
    assert "thought_signature" not in json.dumps(first)


def test_parse_salvage_raw_decode_and_stack_reclose(tmp_path: Path) -> None:
    _result, out, preview, manifest, rows = run_preflight_fixture(tmp_path)
    paths = step7_paths(out)
    strict = json.dumps(output_payload(literal_ko="엄격 직역이다.", natural_ko="엄격 자연역이다."), ensure_ascii=False)
    raw_decode = json.dumps(output_payload(literal_ko="raw 직역이다.", natural_ko="raw 자연역이다."), ensure_ascii=False) + "\ntrailing"
    stack = json.dumps(output_payload(literal_ko="stack 직역이다.", natural_ko="stack 자연역이다."), ensure_ascii=False)[:-1]
    raw = [result_line(rows[0]["key"], strict), result_line(rows[1]["key"], raw_decode), result_line(rows[2]["key"], stack)]
    raw.extend(result_line(row["key"]) for row in rows[3:])
    write_jsonl(paths.raw_results, raw)
    parse_live_results(request_preview_path=preview, manifest_path=manifest, out_dir=out)
    report = json.loads(paths.parse_report.read_text(encoding="utf-8"))
    assert report["strict_json_count"] >= 998
    assert report["raw_decode_count"] == 1
    assert report["stack_reclose_count"] == 1


def test_salvage_content_preservation_guard_rejects_string_mutation() -> None:
    parsed = output_payload(literal_ko="새 문자열", natural_ko="자연역")
    assert content_preservation_guard(parsed, json.dumps(parsed, ensure_ascii=False))
    assert not content_preservation_guard(parsed, '{"literal_ko":"다른 문자열","natural_ko":"자연역"}')


def test_qa_classifies_retry_blocking_advisory_and_khandha_false_positive() -> None:
    bracket = {**output_payload(literal_ko="[그것은] 직역이다."), "stable_segment_key": "b", "original_text": "dhamma", "schema_valid": True, "status": "succeeded"}
    source_bracket = {**output_payload(literal_ko="[66] 직역이다."), "stable_segment_key": "sb", "original_text": "[66] 6. title", "schema_valid": True, "status": "succeeded"}
    hanja_bracket = {**output_payload(literal_ko="[善趣] 직역이다."), "stable_segment_key": "hb", "original_text": "sugati", "schema_valid": True, "status": "succeeded"}
    insertion = {**output_payload(natural_ko="세속적인 일을 즐김이다."), "stable_segment_key": "vri:romn:abh02m.mul:a8d464d40a45", "original_text": "kammārāmatā", "terms": [{"pali": "kammārāmatā", "ko": "일을 즐김"}], "schema_valid": True, "status": "succeeded"}
    omission = {**output_payload(), "stable_segment_key": "vri:romn:s0508a1.att:8b9574445272", "original_text": "accenti", "schema_valid": True, "status": "succeeded"}
    negation = {**output_payload(natural_ko="번뇌를 동반하지 않으며"), "stable_segment_key": "vri:romn:abh03m11.mul:4ab6e93ef3c3", "original_text": "pahātabbahetuka", "schema_valid": True, "status": "succeeded"}
    glossary = {**output_payload(natural_ko="통찰지를 위로 하는"), "stable_segment_key": "g", "original_text": "paññuttara", "schema_valid": True, "status": "succeeded"}
    advisory = {**output_payload(natural_ko="맥락 없는 들어감"), "stable_segment_key": "a", "original_text": "otaraṇā", "schema_valid": True, "status": "succeeded"}
    khandha_false = {**output_payload(natural_ko="무리와 어울린다."), "stable_segment_key": "k", "original_text": "saṅgaṇikārāmatā", "terms": [{"pali": "kammārāmatā", "ko": "일을 즐김"}], "schema_valid": True, "status": "succeeded"}
    khandha_real = {**output_payload(natural_ko="다섯 무리이다."), "stable_segment_key": "kr", "original_text": "pañcakkhandhā", "terms": [{"pali": "khandha", "ko": "무리"}], "schema_valid": True, "status": "succeeded"}
    assert classify_item_gate(bracket)["status"] == "FAIL_RETRY_ONLY"
    assert classify_item_gate(source_bracket)["status"] == "PASS"
    assert classify_item_gate(hanja_bracket)["status"] == "PASS"
    assert classify_item_gate(hanja_bracket)["advisory_warnings"][0]["type"] == "bracket_advisory"
    for item in (insertion, omission, negation, glossary, khandha_real):
        assert classify_item_gate(item)["status"] == "FAIL_BLOCKING"
    assert classify_item_gate(advisory)["status"] == "PASS"
    assert classify_item_gate(khandha_false)["status"] == "PASS"


def test_qa_report_and_retry_plan_outputs_are_created(tmp_path: Path) -> None:
    _result, out, preview, manifest, rows = run_preflight_fixture(tmp_path)
    paths = step7_paths(out)
    raw = []
    for index, row in enumerate(rows):
        payload = output_payload()
        if index == 0:
            payload["literal_ko"] = "[그것은] 직역이다."
        raw.append(result_line(row["key"], json.dumps(payload, ensure_ascii=False)))
    write_jsonl(paths.raw_results, raw)
    parse_live_results(request_preview_path=preview, manifest_path=manifest, out_dir=out)
    qa_result = run_qa(out_dir=out)
    assert qa_result["counts"]["FAIL_RETRY_ONLY"] == 1
    report = report_outputs(out_dir=out)
    retry = build_retry_bracket_plan(out_dir=out)
    assert report["status"] == "REPORTED"
    assert paths.summary_json.exists()
    assert paths.translation_outputs_md.exists()
    assert paths.manual_review_sheet_md.exists()
    assert "raw response" not in paths.summary_md.read_text(encoding="utf-8").lower()
    assert retry["retry_item_count"] == 1
    assert retry["status"] == "READY"


def test_retry_plan_blocks_when_blocking_failures_exist(tmp_path: Path) -> None:
    _result, out, preview, manifest, rows = run_preflight_fixture(tmp_path)
    paths = step7_paths(out)
    raw = []
    for index, row in enumerate(rows):
        payload = output_payload()
        if index == 0:
            payload["literal_ko"] = "[그것은] 직역이다."
            payload["natural_ko"] = "세속적인 일을 즐김이다."
            row["metadata"]["original_text"] = "kammārāmatā"
        raw.append(result_line(row["key"], json.dumps(payload, ensure_ascii=False)))
    write_jsonl(preview, rows)
    write_jsonl(paths.raw_results, raw)
    parse_live_results(request_preview_path=preview, manifest_path=manifest, out_dir=out)
    run_qa(out_dir=out)
    retry = build_retry_bracket_plan(out_dir=out)
    assert retry["status"] == "BLOCKED"


def test_default_cli_runs_preflight_only_and_raw_results_path_is_gitignored(tmp_path: Path, capsys) -> None:
    out, preview, manifest, _rows = make_live_fixture(tmp_path)
    code = live_main(["--request-preview", str(preview), "--manifest", str(manifest), "--out", str(out)])
    captured = capsys.readouterr()
    assert code == 0
    assert '"status": "PASS"' in captured.out
    assert not step7_paths(out).submit_run_manifest.exists()


def test_local_pilot_1000_parsed_checker_smoke_if_available() -> None:
    parsed_path = Path("data/reports/pali/pilot_1000_batch/pilot_1000_parsed.json")
    if not parsed_path.exists():
        pytest.skip("local pilot_1000_parsed.json is not available")
    parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
    blocking = []
    retry = []
    khandha_advisory = []
    for item in parsed.get("items") or []:
        classification = classify_item_gate(item)
        blocking.extend(classification["blocking_failures"])
        retry.extend(classification["retry_only_failures"])
        gates = evaluate_d_arm_item(item)
        for detail in gates.get("advisory_glossary_warning_details") or []:
            if detail == "khandha:무리":
                khandha_advisory.append(item.get("stable_segment_key"))
        for failure in classification["retry_only_failures"]:
            if failure["type"] == "bracket_violation":
                assert all(
                    isinstance(detail, dict) and detail.get("bracket_type") == "SUPPLIED_KOREAN"
                    for detail in failure.get("details") or []
                )
    assert blocking == []
    assert len(khandha_advisory) == 5
    assert retry
