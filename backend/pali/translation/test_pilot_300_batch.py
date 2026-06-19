import argparse
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from backend.pali.scripts.build_pilot_300_manifest import selection_content_sha256
from backend.pali.scripts.run_pilot_300_batch import (
    batch_paths,
    build_parser,
    file_sha256,
    normalize_model_name,
    read_json,
    run,
)


ENV_NAMES = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY", "PALI_GEMINI_API_KEY")

VALID_TRANSLATION = {
    "literal_ko": "직역",
    "natural_ko": "자연역",
    "terms": [],
    "grammar_notes": [],
    "doctrinal_notes": [],
    "uncertainties": [],
    "quality_flags": [],
}


class FakeBatchClient:
    def __init__(self, *, create_response=None, status=None):
        self.create_response = create_response or {
            "name": "batches/pilot-300-test",
            "done": False,
            "metadata": {"state": "BATCH_STATE_PENDING"},
        }
        self.status = status or {
            "name": "batches/pilot-300-test",
            "done": True,
            "metadata": {"state": "BATCH_STATE_SUCCEEDED"},
            "inlineResponses": [result_line("seg-000")],
        }
        self.created_requests = []
        self.get_calls = []

    def create_inline_batch(self, *, model, requests, display_name):
        self.created_requests.append({"model": model, "requests": requests, "display_name": display_name})
        return self.create_response

    def get_batch(self, provider_batch_id):
        self.get_calls.append(provider_batch_id)
        return self.status


@contextmanager
def patched_env(**values):
    old = {name: os.environ.get(name) for name in ENV_NAMES}
    for name in ENV_NAMES:
        os.environ.pop(name, None)
    for name, value in values.items():
        os.environ[name] = value
    try:
        yield
    finally:
        for name in ENV_NAMES:
            os.environ.pop(name, None)
            if old[name] is not None:
                os.environ[name] = old[name]


def provider_line(index):
    key = f"seg-{index:03d}"
    return {
        "key": key,
        "request": {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"빠알리 원문:\n<<<\nsource text {index}\n>>>"}],
                }
            ],
            "generation_config": {"temperature": 0.2, "response_mime_type": "application/json"},
        },
    }


def manifest_item(index):
    key = f"seg-{index:03d}"
    return {
        "stable_segment_key": key,
        "source_text_hash": f"hash-{key}",
        "source_path": f"romn/s05{index:03d}m.mul.xml",
        "text_layer": "mula" if index % 3 == 0 else "atthakatha" if index % 3 == 1 else "tika",
        "chunk_type": "verse" if index % 5 == 0 else "prose",
        "length_bucket": "long" if index % 7 == 0 else "medium",
        "selection_group": "hard" if index < 100 else "representative",
        "selection_bucket": "tika_long" if index < 100 else "representative_stratified",
        "estimated_cost_usd": "0.001000",
    }


def valid_translation_text():
    return json.dumps(VALID_TRANSLATION, ensure_ascii=False)


def result_line(key, *, response=None, error=None):
    if error is not None:
        return {"metadata": {"key": key}, "error": error}
    return {
        "metadata": {"key": key},
        "response": response
        or {
            "candidates": [{"content": {"parts": [{"text": valid_translation_text()}]}}],
            "usageMetadata": {
                "promptTokenCount": 100,
                "candidatesTokenCount": 20,
                "thoughtsTokenCount": 30,
                "totalTokenCount": 150,
            },
        },
    }


def schema_invalid_result_line(key):
    payload = dict(VALID_TRANSLATION)
    payload.pop("natural_ko")
    return {
        "metadata": {"key": key},
        "response": {
            "candidates": [{"content": {"parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}}],
            "usageMetadata": {
                "promptTokenCount": 100,
                "candidatesTokenCount": 20,
                "thoughtsTokenCount": 30,
                "totalTokenCount": 150,
            },
        },
    }


def write_fixture(root_path):
    root = Path(root_path)
    provider_lines = [provider_line(index) for index in range(300)]
    items = [manifest_item(index) for index in range(300)]
    manifest = {
        "schema_version": "pali_pilot_300_manifest_v1",
        "source_provenance": {"source_commit": "49bc86914748589a2501b548cc6b3e97a8abe018"},
        "summary": {"selected_count": 300, "hard_count": 100, "representative_count": 200},
        "items": items,
    }
    selection_sha = selection_content_sha256(manifest)
    paths = {
        "manifest": root / "pilot_300_manifest.json",
        "readiness": root / "readiness.json",
        "smoke": root / "smoke.json",
        "jsonl": root / "batch_unsubmitted.jsonl",
        "jsonl_manifest": root / "batch_unsubmitted_manifest.json",
        "cost": root / "cost.json",
        "source_integrity": root / "source_integrity.json",
        "out": root / "reports",
        "qa_out": root / "qa_report",
    }
    paths["manifest"].write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    paths["readiness"].write_text(
        json.dumps({"readiness_status": "PASS_READY_FOR_USER_APPROVAL", "batch_submission_allowed_now": False}),
        encoding="utf-8",
    )
    paths["smoke"].write_text(
        json.dumps(
            {
                "status": "PASS",
                "sample_count_attempted": 5,
                "sample_count_succeeded": 5,
                "schema_valid_count": 5,
                "parse_failed_count": 0,
                "batch_submission_allowed_now": False,
                "observed_model_versions": ["gemini-3.1-pro-preview"],
                "warnings": ["model_version_drift"],
            }
        ),
        encoding="utf-8",
    )
    paths["jsonl"].write_text(
        "\n".join(json.dumps(line, ensure_ascii=False) for line in provider_lines) + "\n",
        encoding="utf-8",
    )
    paths["jsonl_manifest"].write_text(
        json.dumps(
            {
                "request_count": 300,
                "jsonl_sha256": file_sha256(paths["jsonl"]),
                "items": items,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    paths["cost"].write_text(
        json.dumps({"estimate_totals": {"conservative_gate": {"cost_usd": "8.459241"}}}),
        encoding="utf-8",
    )
    paths["source_integrity"].write_text(json.dumps({"valid": True}), encoding="utf-8")
    return paths, selection_sha


def args_for(paths, mode="dry-run", selection_sha=None, **overrides):
    data = {
        "mode": mode,
        "manifest": str(paths["manifest"]),
        "readiness": str(paths["readiness"]),
        "smoke_results": str(paths["smoke"]),
        "jsonl": str(paths["jsonl"]),
        "jsonl_manifest": str(paths["jsonl_manifest"]),
        "cost_estimate": str(paths["cost"]),
        "source_integrity": str(paths["source_integrity"]),
        "batch_run_manifest": None,
        "provider_batch_id": None,
        "raw_results": None,
        "parsed": None,
        "summary": None,
        "out": str(paths["out"]),
        "qa_out": str(paths["qa_out"]),
        "gold": "data/gold_set.json",
        "glossary_qa": "data/reports/pali/translation_qa_v1_1_baseline_49bc869.json",
        "expected_selection_sha": selection_sha,
        "budget_usd": "20",
        "model": "models/gemini-3.1-pro-preview",
        "enable_submit": False,
        "user_green_light": False,
        "timeout_seconds": 1,
        "pretty": True,
    }
    data.update(overrides)
    return argparse.Namespace(**data)


class Pilot300BatchHarnessTests(unittest.TestCase):
    def test_dry_run_passes_without_network_or_credential(self):
        with tempfile.TemporaryDirectory() as tmp, patched_env():
            paths, selection_sha = write_fixture(tmp)
            result = run(args_for(paths, selection_sha=selection_sha))
            self.assertEqual(result["status"], "DRY_RUN_PASS")
            self.assertTrue((paths["out"] / "pilot_300_batch_dry_run.json").exists())
            self.assertTrue((paths["out"] / "pilot_300_batch_submit_plan.md").exists())
            self.assertTrue((paths["out"] / "pilot_300_batch_run_manifest.json").exists())
            manifest = read_json(paths["out"] / "pilot_300_batch_run_manifest.json")
            self.assertFalse(manifest["credential_present"])

    def test_submit_gate_blocks_flags_credential_and_hashes(self):
        with tempfile.TemporaryDirectory() as tmp, patched_env():
            paths, selection_sha = write_fixture(tmp)
            result = run(args_for(paths, mode="submit", selection_sha=selection_sha), client=FakeBatchClient())
            self.assertIn("BLOCKED_SUBMIT_NOT_ENABLED", result["blocking_reasons"])
            self.assertIn("BLOCKED_USER_GREEN_LIGHT_REQUIRED", result["blocking_reasons"])
            self.assertIn("BLOCKED_MISSING_GEMINI_CREDENTIAL", result["blocking_reasons"])
        with tempfile.TemporaryDirectory() as tmp, patched_env(PALI_GEMINI_API_KEY="dummy"):
            paths, selection_sha = write_fixture(tmp)
            result = run(
                args_for(
                    paths,
                    mode="submit",
                    selection_sha="bad",
                    enable_submit=True,
                    user_green_light=True,
                ),
                client=FakeBatchClient(),
            )
            self.assertIn("BLOCKED_HASH_MISMATCH", result["blocking_reasons"])

    def test_submit_gate_blocks_invalid_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp, patched_env(PALI_GEMINI_API_KEY="dummy"):
            paths, selection_sha = write_fixture(tmp)
            paths["readiness"].write_text(json.dumps({"readiness_status": "FAIL", "batch_submission_allowed_now": False}), encoding="utf-8")
            result = run(args_for(paths, mode="submit", selection_sha=selection_sha, enable_submit=True, user_green_light=True), client=FakeBatchClient())
            self.assertIn("BLOCKED_READINESS_NOT_PASS", result["blocking_reasons"])
        with tempfile.TemporaryDirectory() as tmp, patched_env(PALI_GEMINI_API_KEY="dummy"):
            paths, selection_sha = write_fixture(tmp)
            paths["readiness"].write_text(json.dumps({"readiness_status": "PASS_READY_FOR_USER_APPROVAL", "batch_submission_allowed_now": True}), encoding="utf-8")
            result = run(args_for(paths, mode="submit", selection_sha=selection_sha, enable_submit=True, user_green_light=True), client=FakeBatchClient())
            self.assertIn("BLOCKED_UNSAFE_BATCH_FLAG", result["blocking_reasons"])
        with tempfile.TemporaryDirectory() as tmp, patched_env(PALI_GEMINI_API_KEY="dummy"):
            paths, selection_sha = write_fixture(tmp)
            paths["smoke"].write_text(json.dumps({"status": "FAIL", "sample_count_attempted": 5, "sample_count_succeeded": 0, "schema_valid_count": 0, "parse_failed_count": 1}), encoding="utf-8")
            result = run(args_for(paths, mode="submit", selection_sha=selection_sha, enable_submit=True, user_green_light=True), client=FakeBatchClient())
            self.assertIn("BLOCKED_SMOKE_NOT_PASS", result["blocking_reasons"])
            self.assertIn("BLOCKED_SMOKE_SCHEMA_OR_PARSE_FAILURE", result["blocking_reasons"])
        with tempfile.TemporaryDirectory() as tmp, patched_env(PALI_GEMINI_API_KEY="dummy"):
            paths, selection_sha = write_fixture(tmp)
            paths["source_integrity"].write_text(json.dumps({"valid": False}), encoding="utf-8")
            result = run(args_for(paths, mode="submit", selection_sha=selection_sha, enable_submit=True, user_green_light=True), client=FakeBatchClient())
            self.assertIn("BLOCKED_SOURCE_INTEGRITY", result["blocking_reasons"])

    def test_submit_gate_blocks_jsonl_count_hash_and_budget(self):
        with tempfile.TemporaryDirectory() as tmp, patched_env(PALI_GEMINI_API_KEY="dummy"):
            paths, selection_sha = write_fixture(tmp)
            data = read_json(paths["jsonl_manifest"])
            data["jsonl_sha256"] = "bad"
            paths["jsonl_manifest"].write_text(json.dumps(data), encoding="utf-8")
            result = run(args_for(paths, mode="submit", selection_sha=selection_sha, enable_submit=True, user_green_light=True), client=FakeBatchClient())
            self.assertIn("BLOCKED_JSONL_HASH_MISMATCH", result["blocking_reasons"])
        with tempfile.TemporaryDirectory() as tmp, patched_env(PALI_GEMINI_API_KEY="dummy"):
            paths, selection_sha = write_fixture(tmp)
            data = read_json(paths["jsonl_manifest"])
            data["request_count"] = 299
            paths["jsonl_manifest"].write_text(json.dumps(data), encoding="utf-8")
            result = run(args_for(paths, mode="submit", selection_sha=selection_sha, enable_submit=True, user_green_light=True), client=FakeBatchClient())
            self.assertIn("BLOCKED_JSONL_COUNT_MISMATCH", result["blocking_reasons"])
        with tempfile.TemporaryDirectory() as tmp, patched_env(PALI_GEMINI_API_KEY="dummy"):
            paths, selection_sha = write_fixture(tmp)
            result = run(args_for(paths, mode="submit", selection_sha=selection_sha, budget_usd="8", enable_submit=True, user_green_light=True), client=FakeBatchClient())
            self.assertIn("BLOCKED_OVER_BUDGET", result["blocking_reasons"])

    def test_submit_success_records_provider_id_and_second_submit_blocks(self):
        with tempfile.TemporaryDirectory() as tmp, patched_env(PALI_GEMINI_API_KEY="dummy-secret"):
            paths, selection_sha = write_fixture(tmp)
            client = FakeBatchClient()
            args = args_for(paths, mode="submit", selection_sha=selection_sha, enable_submit=True, user_green_light=True)
            result = run(args, client=client)
            self.assertEqual(result["status"], "SUBMITTED_PROVIDER_BATCH_ID_RECORDED")
            self.assertEqual(len(client.created_requests[0]["requests"]), 300)
            run_manifest_text = (paths["out"] / "pilot_300_batch_run_manifest.json").read_text(encoding="utf-8")
            self.assertIn("batches/pilot-300-test", run_manifest_text)
            self.assertNotIn("dummy-secret", run_manifest_text)
            self.assertTrue((paths["out"] / ".pilot_300_v1_batch_submitted.lock").exists())
            second = run(args, client=FakeBatchClient())
            self.assertEqual(second["status"], "BLOCKED_ALREADY_SUBMITTED")

    def test_existing_manifest_or_sentinel_blocks_double_submit(self):
        with tempfile.TemporaryDirectory() as tmp, patched_env(PALI_GEMINI_API_KEY="dummy"):
            paths, selection_sha = write_fixture(tmp)
            out_paths = batch_paths(paths["out"])
            out_paths.out_dir.mkdir(parents=True)
            out_paths.run_manifest.write_text(json.dumps({"provider_batch_id": "batches/existing"}), encoding="utf-8")
            result = run(args_for(paths, mode="submit", selection_sha=selection_sha, enable_submit=True, user_green_light=True), client=FakeBatchClient())
            self.assertEqual(result["status"], "BLOCKED_ALREADY_SUBMITTED")
        with tempfile.TemporaryDirectory() as tmp, patched_env(PALI_GEMINI_API_KEY="dummy"):
            paths, selection_sha = write_fixture(tmp)
            out_paths = batch_paths(paths["out"])
            out_paths.out_dir.mkdir(parents=True)
            out_paths.sentinel.write_text(json.dumps({"provider_batch_id": "batches/existing"}), encoding="utf-8")
            result = run(args_for(paths, mode="submit", selection_sha=selection_sha, enable_submit=True, user_green_light=True), client=FakeBatchClient())
            self.assertEqual(result["status"], "BLOCKED_ALREADY_SUBMITTED")

    def test_poll_fetch_recovery_with_provider_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, selection_sha = write_fixture(tmp)
            client = FakeBatchClient()
            poll = run(args_for(paths, mode="poll", selection_sha=selection_sha, provider_batch_id="batches/recover"), client=client)
            self.assertEqual(poll["status"], "POLL_STATUS_WRITTEN")
            fetch = run(args_for(paths, mode="fetch", selection_sha=selection_sha, provider_batch_id="batches/recover"), client=client)
            self.assertEqual(fetch["status"], "FETCH_RAW_RESULTS_WRITTEN")
            self.assertTrue((paths["out"] / "pilot_300_batch_raw_results.jsonl").exists())
            self.assertEqual(client.get_calls, ["batches/recover", "batches/recover"])

    def test_parse_maps_results_and_summarizes_partial_failure_without_resubmit(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, selection_sha = write_fixture(tmp)
            run(args_for(paths, selection_sha=selection_sha))
            raw_path = paths["out"] / "pilot_300_batch_raw_results.jsonl"
            raw_path.write_text(
                "\n".join(
                    json.dumps(line, ensure_ascii=False)
                    for line in [
                        result_line("seg-000"),
                        result_line("seg-001", error={"code": 500, "message": "provider failed"}),
                        schema_invalid_result_line("seg-002"),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            run_manifest = read_json(paths["out"] / "pilot_300_batch_run_manifest.json")
            run_manifest["provider_batch_id"] = "batches/parse-test"
            (paths["out"] / "pilot_300_batch_run_manifest.json").write_text(json.dumps(run_manifest), encoding="utf-8")
            result = run(args_for(paths, mode="parse", selection_sha=selection_sha))
            self.assertEqual(result["status"], "PARSED")
            summary = read_json(paths["out"] / "pilot_300_batch_summary.json")
            self.assertIn("partial_failure_no_automatic_resubmit", summary["warnings"])
            self.assertFalse(summary["automatic_resubmit_allowed"])
            parsed = read_json(paths["out"] / "pilot_300_batch_parsed.json")
            by_key = {item["stable_segment_key"]: item for item in parsed["items"]}
            self.assertEqual(by_key["seg-000"]["status"], "succeeded")
            self.assertEqual(by_key["seg-001"]["status"], "failed")
            self.assertEqual(by_key["seg-002"]["status"], "schema_invalid")

    def test_qa_mode_invokes_report_generator(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, selection_sha = write_fixture(tmp)
            paths["out"].mkdir(parents=True)
            (paths["out"] / "pilot_300_batch_parsed.json").write_text(json.dumps({"items": []}), encoding="utf-8")
            with patch("backend.pali.scripts.run_pilot_300_batch.subprocess.run") as mocked:
                mocked.return_value.returncode = 0
                mocked.return_value.stdout = "ok"
                mocked.return_value.stderr = ""
                result = run(args_for(paths, mode="qa", selection_sha=selection_sha))
            self.assertEqual(result["status"], "QA_COMPLETE")
            self.assertIn("generate_qa_report", " ".join(mocked.call_args.args[0]))

    def test_model_normalization_and_cli_has_no_api_key(self):
        self.assertEqual(normalize_model_name("models/gemini-3.1-pro-preview"), "gemini-3.1-pro-preview")
        self.assertEqual(normalize_model_name("gemini-3.1-pro-preview"), "gemini-3.1-pro-preview")
        self.assertNotIn("--api-key", build_parser().format_help())


if __name__ == "__main__":
    unittest.main()
