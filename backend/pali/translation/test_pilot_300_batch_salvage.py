import argparse
import json
import tempfile
import unittest
from pathlib import Path

from backend.pali.scripts.salvage_pilot_300_batch_parse import (
    parse_output_cascade,
    run_salvage,
)


VALID_TRANSLATION = {
    "literal_ko": "직역",
    "natural_ko": "자연역",
    "terms": [],
    "grammar_notes": [],
    "doctrinal_notes": [],
    "uncertainties": [],
    "quality_flags": [],
}


class FakeCompleted:
    returncode = 0
    stdout = "ok"
    stderr = ""


def fake_qa_runner(cmd, **_kwargs):
    out_dir = Path(cmd[cmd.index("--out") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "review_report.md").write_text("# QA\n", encoding="utf-8")
    (out_dir / "review_queue.json").write_text("{}", encoding="utf-8")
    (out_dir / "run_manifest.json").write_text(json.dumps({"args": cmd}), encoding="utf-8")
    return FakeCompleted()


def text(payload=None):
    return json.dumps(payload or VALID_TRANSLATION, ensure_ascii=False)


def raw_line(key, output_text, *, finish_reason="STOP", thought_signature=False):
    usage = {
        "promptTokenCount": 10,
        "candidatesTokenCount": 20,
        "thoughtsTokenCount": 30,
        "totalTokenCount": 60,
    }
    if thought_signature:
        usage["promptTokensDetails"] = [{"thoughtSignature": "secret-looking-provider-metadata"}]
    return {
        "metadata": {"key": key},
        "response": {
            "candidates": [
                {
                    "finishReason": finish_reason,
                    "content": {"parts": [{"text": output_text}]},
                }
            ],
            "usageMetadata": usage,
        },
    }


def previous_item(index, *, valid=True):
    key = f"seg-{index:03d}"
    parsed = dict(VALID_TRANSLATION) if valid else None
    return {
        "stable_segment_key": key,
        "source_text_hash": f"hash-{key}",
        "source_path": "romn/s0501m.mul.xml",
        "text_layer": "mula",
        "length_bucket": "medium",
        "chunk_type": "prose",
        "selection_group": "representative",
        "selection_bucket": "representative_stratified",
        "original_text": "anicca dukkha anattā",
        "model_output_raw": text() if valid else "{bad",
        "parsed_translation_json": parsed,
        "schema_valid": valid,
        "parse_failed": not valid,
        "literal_ko": parsed["literal_ko"] if parsed else "",
        "natural_ko": parsed["natural_ko"] if parsed else "",
        "terms": [],
        "grammar_notes": [],
        "doctrinal_notes": [],
        "uncertainties": [],
        "quality_flags": [],
        "local_validator_flags": [] if valid else ["json_parse_failed"],
        "prompt_token_count": 10,
        "candidates_token_count": 20,
        "thoughts_token_count": 30,
        "total_token_count": 60,
        "actual_cost_usd": "0.000250",
        "status": "succeeded" if valid else "schema_invalid",
        "error_message": "" if valid else "JSON parse failed",
    }


def write_fixture(root_path):
    root = Path(root_path)
    raw_lines = []
    items = []
    for index in range(300):
        valid = index < 266
        items.append(previous_item(index, valid=valid))
        key = f"seg-{index:03d}"
        if index < 266:
            output = text()
        elif index < 284:
            output = text() + "\n}\n}\n[]"
        elif index < 299:
            output = text()[:-1]
        else:
            payload = text()
            output = payload[:-1] + "\n]\n}"
        raw_lines.append(raw_line(key, output, thought_signature=index == 266))
    paths = {
        "raw": root / "raw.jsonl",
        "parsed": root / "parsed.json",
        "summary": root / "summary.json",
        "run_manifest": root / "run_manifest.json",
        "provider_status": root / "provider_status.json",
        "out": root / "out",
        "qa_out": root / "qa_salvaged",
    }
    paths["raw"].write_text("\n".join(json.dumps(line, ensure_ascii=False) for line in raw_lines) + "\n", encoding="utf-8")
    paths["parsed"].write_text(json.dumps({"schema_version": "old", "provider_batch_id": "batches/test", "items": items}, ensure_ascii=False), encoding="utf-8")
    paths["summary"].write_text(
        json.dumps(
            {
                "request_count": 300,
                "schema_valid_count": 266,
                "schema_invalid_count": 34,
                "failed_count": 34,
                "actual_cost_usd": "7.949868",
                "estimated_conservative_gate_usd": "8.459241",
                "actual_to_conservative_ratio": "0.940",
                "budget_usd": "20",
                "budget_passed": True,
            }
        ),
        encoding="utf-8",
    )
    paths["run_manifest"].write_text(json.dumps({"provider_batch_id": "batches/test"}), encoding="utf-8")
    paths["provider_status"].write_text(json.dumps({"done": True}), encoding="utf-8")
    return paths


def args_for(paths):
    return argparse.Namespace(
        raw_results=str(paths["raw"]),
        previous_parsed=str(paths["parsed"]),
        previous_summary=str(paths["summary"]),
        run_manifest=str(paths["run_manifest"]),
        provider_status=str(paths["provider_status"]),
        out=str(paths["out"]),
        qa_out=str(paths["qa_out"]),
        gold="data/gold_set.json",
        glossary_qa="data/reports/pali/translation_qa_v1_1_baseline_49bc869.json",
        pretty=True,
    )


class Pilot300BatchSalvageTests(unittest.TestCase):
    def test_parse_cascade_strict_raw_decode_fenced_and_stack_reclose(self):
        strict = parse_output_cascade(text(), finish_reason="STOP")
        self.assertTrue(strict.ok)
        self.assertEqual(strict.method, "strict_json")

        extra = parse_output_cascade(text() + "\n}\n[]", finish_reason="STOP")
        self.assertTrue(extra.ok)
        self.assertEqual(extra.method, "raw_decode")
        self.assertIn("trailing_extra_removed", extra.flags)

        fenced = parse_output_cascade("```json\n" + text() + "\n```", finish_reason="STOP")
        self.assertTrue(fenced.ok)
        self.assertIn("json_fence_removed", fenced.flags)

        missing_brace = parse_output_cascade(text()[:-1], finish_reason="STOP")
        self.assertTrue(missing_brace.ok)
        self.assertEqual(missing_brace.method, "stack_reclose")
        self.assertIn("missing_final_brace_added", missing_brace.flags)

        missing_bracket = parse_output_cascade(
            '{"literal_ko":"직역","natural_ko":"자연역","terms":[{"pali":"dhamma","ko":"법","gloss":"","note":""},"grammar_notes":[],"doctrinal_notes":[],"uncertainties":[],"quality_flags":[]',
            finish_reason="STOP",
        )
        self.assertFalse(missing_bracket.ok)

        bracket_missing = parse_output_cascade(
            '{"literal_ko":"직역","natural_ko":"자연역","terms":[],"grammar_notes":["x"],"doctrinal_notes":[],"uncertainties":[],"quality_flags":[]',
            finish_reason="STOP",
        )
        self.assertTrue(bracket_missing.ok)
        self.assertEqual(bracket_missing.method, "stack_reclose")

        mismatch = parse_output_cascade(text()[:-1] + "\n]\n}", finish_reason="STOP")
        self.assertTrue(mismatch.ok)
        self.assertEqual(mismatch.method, "stack_reclose")
        self.assertIn("final_bracket_misclose_repaired", mismatch.flags)

    def test_unsafe_and_completeness_failures_are_not_salvaged(self):
        unsafe = parse_output_cascade('{"literal_ko":"직역 " broken","natural_ko":"자연역","terms":[],"grammar_notes":[],"doctrinal_notes":[],"uncertainties":[],"quality_flags":[]', finish_reason="STOP")
        self.assertFalse(unsafe.ok)

        missing_required = dict(VALID_TRANSLATION)
        missing_required.pop("natural_ko")
        result = parse_output_cascade(text(missing_required), finish_reason="STOP")
        self.assertFalse(result.ok)
        self.assertIn("completeness_gate_failed", result.flags)

        empty_literal = dict(VALID_TRANSLATION)
        empty_literal["literal_ko"] = ""
        result = parse_output_cascade(text(empty_literal), finish_reason="STOP")
        self.assertFalse(result.ok)

        max_tokens = parse_output_cascade(text(), finish_reason="MAX_TOKENS")
        self.assertFalse(max_tokens.ok)
        self.assertIn("finish_reason_max_tokens", max_tokens.flags)

    def test_salvage_run_writes_full_300_and_preserves_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_fixture(tmp)
            original_raw = paths["raw"].read_text(encoding="utf-8")
            original_parsed = paths["parsed"].read_text(encoding="utf-8")
            original_summary = paths["summary"].read_text(encoding="utf-8")
            result = run_salvage(args_for(paths), qa_runner=fake_qa_runner)
            self.assertEqual(result["status"], "SALVAGE_COMPLETE")
            self.assertEqual(result["api_calls_made"], 0)
            parsed = json.loads((paths["out"] / "pilot_300_batch_parsed_salvaged.json").read_text(encoding="utf-8"))
            summary = json.loads((paths["out"] / "pilot_300_batch_summary_salvaged.json").read_text(encoding="utf-8"))
            self.assertEqual(len(parsed["items"]), 300)
            self.assertEqual(summary["before"]["schema_valid"], 266)
            self.assertEqual(summary["after"]["schema_valid"], 300)
            self.assertEqual(summary["recovered_count"], 34)
            self.assertEqual(summary["unrecovered_count"], 0)
            self.assertEqual(summary["recovered_by_method"], {"raw_decode": 18, "stack_reclose": 16})
            self.assertEqual(summary["api_calls_made"], 0)
            self.assertEqual(summary["cost"]["new_api_spend_usd"], "0.000000")
            self.assertEqual(summary["strict_payload_preservation"]["strict_items_checked"], 266)
            self.assertEqual(summary["strict_payload_preservation"]["strict_translation_payload_changed"], 0)
            self.assertTrue(all(item["parse_method"] == "strict_json" for item in parsed["items"][:266]))
            self.assertTrue(all(item["recovered_via"] == "none" for item in parsed["items"][:266]))
            self.assertTrue(all(item["salvage_applied"] is False for item in parsed["items"][:266]))
            self.assertIn("model_output_salvaged", parsed["items"][266])
            self.assertEqual(paths["raw"].read_text(encoding="utf-8"), original_raw)
            self.assertEqual(paths["parsed"].read_text(encoding="utf-8"), original_parsed)
            self.assertEqual(paths["summary"].read_text(encoding="utf-8"), original_summary)
            self.assertTrue((paths["qa_out"] / "review_report.md").exists())
            report = (paths["out"] / "pilot_300_batch_salvage_report.md").read_text(encoding="utf-8")
            self.assertNotIn("secret-looking-provider-metadata", report)

    def test_unrecovered_is_retry_candidate_without_api_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_fixture(tmp)
            lines = [json.loads(line) for line in paths["raw"].read_text(encoding="utf-8").splitlines()]
            lines[-1] = raw_line("seg-299", '{"literal_ko":"직역 " broken"', finish_reason="STOP")
            paths["raw"].write_text("\n".join(json.dumps(line, ensure_ascii=False) for line in lines) + "\n", encoding="utf-8")
            result = run_salvage(args_for(paths), qa_runner=fake_qa_runner)
            summary = json.loads((paths["out"] / "pilot_300_batch_summary_salvaged.json").read_text(encoding="utf-8"))
            self.assertEqual(result["api_calls_made"], 0)
            self.assertEqual(summary["unrecovered_count"], 1)
            self.assertEqual(summary["retry_candidates"], ["seg-299"])
            parsed = json.loads((paths["out"] / "pilot_300_batch_parsed_salvaged.json").read_text(encoding="utf-8"))
            self.assertTrue(parsed["items"][-1]["retry_candidate"])
            self.assertFalse(parsed["items"][-1]["automatic_resubmit_allowed"])


if __name__ == "__main__":
    unittest.main()
