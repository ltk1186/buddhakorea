import argparse
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from backend.pali.scripts.run_pilot_300_live_smoke import (
    ProviderError,
    build_parser,
    decimal_ratio,
    read_jsonl,
    run_live_smoke,
    select_smoke_samples,
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


class FakeClient:
    def __init__(self, responses=None, errors=None):
        self.responses = list(responses or [])
        self.errors = list(errors or [])
        self.calls = []

    def generate_content(self, *, model, payload):
        self.calls.append({"model": model, "payload": payload})
        if self.errors:
            error = self.errors.pop(0)
            if error is not None:
                raise error
        if self.responses:
            return self.responses.pop(0)
        return success_response()


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


def success_response(**overrides):
    response = {
        "modelVersion": "models/gemini-3.1-pro-preview",
        "candidates": [
            {
                "content": {
                    "parts": [{"text": json.dumps(VALID_TRANSLATION, ensure_ascii=False)}]
                }
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 100,
            "candidatesTokenCount": 20,
            "thoughtsTokenCount": 30,
            "totalTokenCount": 150,
        },
    }
    response.update(overrides)
    return response


def schema_invalid_response():
    bad = dict(VALID_TRANSLATION)
    bad.pop("natural_ko")
    return {
        "modelVersion": "models/gemini-3.1-pro-preview",
        "candidates": [{"content": {"parts": [{"text": json.dumps(bad, ensure_ascii=False)}]}}],
        "usageMetadata": {
            "promptTokenCount": 100,
            "candidatesTokenCount": 20,
            "thoughtsTokenCount": 30,
            "totalTokenCount": 150,
        },
    }


def write_fixture(tmp):
    root = Path(tmp)
    manifest_items = [
        item("seg-tika", "tika_long", "tika", "long", "prose", "romn/s0403t.tik.xml", "hard"),
        item("seg-att", "atthakatha_long", "atthakatha", "long", "prose", "romn/s0101a.att.xml", "hard"),
        item("seg-s05", "verse", "mula", "medium", "verse", "romn/s0501m.mul.xml", "hard", ["glossary_risk"]),
        item("seg-abh", "abhidhamma_definition", "mula", "medium", "prose", "romn/abh01m.mul.xml", "hard"),
        item("seg-rep", "representative_stratified", "mula", "short", "prose", "romn/s0201m.mul.xml", "representative"),
        item("seg-heading", "heading_title_probe", "mula", "short", "heading", "romn/s0301m.mul.xml", "representative"),
        item("seg-holdout", "representative_stratified", "mula", "short", "prose", "romn/s0502m.mul.xml", "representative", gold=True),
    ]
    manifest = {
        "schema_version": "pali_pilot_300_manifest_v1",
        "summary": {"selected_count": 300, "hard_count": 100, "representative_count": 200},
        "items": manifest_items,
    }
    from backend.pali.scripts.build_pilot_300_manifest import selection_content_sha256

    selection_sha = selection_content_sha256(manifest)
    readiness = {
        "readiness_status": "PASS_READY_FOR_USER_APPROVAL",
        "batch_submission_allowed_now": False,
    }
    lines = []
    sidecar_items = []
    cost_items = []
    for index, manifest_item in enumerate(manifest_items):
        key = manifest_item["stable_segment_key"]
        lines.append(
            {
                "key": key,
                "request": {
                    "contents": [{"role": "user", "parts": [{"text": f"prompt for {key}"}]}],
                    "generation_config": {"temperature": 0.2, "response_mime_type": "application/json"},
                },
            }
        )
        sidecar_items.append(
            {
                "stable_segment_key": key,
                "jsonl_line_index": index,
                "source_text_hash": manifest_item["source_text_hash"],
            }
        )
        cost_items.append(
            {
                "stable_segment_key": key,
                "planning_p90": {
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "thinking_tokens": 30,
                    "official_cost_usd": "0.000400",
                },
            }
        )
    paths = {
        "manifest": root / "manifest.json",
        "readiness": root / "readiness.json",
        "jsonl": root / "batch.jsonl",
        "jsonl_manifest": root / "batch_manifest.json",
        "cost_estimate": root / "cost.json",
        "out": root / "out",
    }
    paths["manifest"].write_text(json.dumps(manifest), encoding="utf-8")
    paths["readiness"].write_text(json.dumps(readiness), encoding="utf-8")
    paths["jsonl"].write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    paths["jsonl_manifest"].write_text(json.dumps({"items": sidecar_items}), encoding="utf-8")
    paths["cost_estimate"].write_text(json.dumps({"items": cost_items}), encoding="utf-8")
    return paths, manifest, selection_sha


def item(key, bucket, layer, length, chunk, source_path, group, tags=None, gold=False):
    return {
        "stable_segment_key": key,
        "source_text_hash": f"hash-{key}",
        "text_layer": layer,
        "length_bucket": length,
        "chunk_type": chunk,
        "selection_group": group,
        "selection_bucket": bucket,
        "secondary_tags": tags or [],
        "source_path": source_path,
        "gold_candidate": gold,
        "pool_candidate": "holdout_gold" if gold else None,
        "do_not_use_for_tuning_until_reviewed": gold,
    }


def args_for(paths, selection_sha, **overrides):
    data = {
        "manifest": str(paths["manifest"]),
        "readiness": str(paths["readiness"]),
        "jsonl": str(paths["jsonl"]),
        "jsonl_manifest": str(paths["jsonl_manifest"]),
        "cost_estimate": str(paths["cost_estimate"]),
        "out": str(paths["out"]),
        "max_segments": 5,
        "budget_usd": "0.50",
        "expected_selection_sha": selection_sha,
        "model": "models/gemini-3.1-pro-preview",
        "timeout_seconds": 1,
        "max_attempts_per_segment": 3,
        "retry_backoff_seconds": 0,
        "enable_smoke": True,
        "user_green_light": True,
        "pretty": True,
    }
    data.update(overrides)
    return argparse.Namespace(**data)


class Pilot300LiveSmokeTests(unittest.TestCase):
    def test_gate_flags_and_credential_blocks(self):
        with tempfile.TemporaryDirectory() as tmp, patched_env():
            paths, _manifest, selection_sha = write_fixture(tmp)
            result = run_live_smoke(args_for(paths, selection_sha, enable_smoke=False), client=FakeClient())
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn("BLOCKED_SMOKE_NOT_ENABLED", result["blocking_reasons"])
            self.assertIn("BLOCKED_MISSING_GEMINI_CREDENTIAL", result["blocking_reasons"])
            result = run_live_smoke(args_for(paths, selection_sha, user_green_light=False), client=FakeClient())
            self.assertIn("BLOCKED_USER_GREEN_LIGHT_REQUIRED", result["blocking_reasons"])

    def test_max_segments_budget_readiness_and_hash_gates(self):
        with tempfile.TemporaryDirectory() as tmp, patched_env(GEMINI_API_KEY="dummy"):
            paths, _manifest, selection_sha = write_fixture(tmp)
            self.assertIn("BLOCKED_TOO_MANY_SEGMENTS", run_live_smoke(args_for(paths, selection_sha, max_segments=6), client=FakeClient())["blocking_reasons"])
            self.assertIn("BLOCKED_SMOKE_BUDGET_TOO_HIGH", run_live_smoke(args_for(paths, selection_sha, budget_usd="0.51"), client=FakeClient())["blocking_reasons"])
            self.assertIn("BLOCKED_HASH_MISMATCH", run_live_smoke(args_for(paths, selection_sha, expected_selection_sha="bad"), client=FakeClient())["blocking_reasons"])
            paths["readiness"].write_text(json.dumps({"readiness_status": "FAIL", "batch_submission_allowed_now": False}), encoding="utf-8")
            self.assertIn("BLOCKED_READINESS_NOT_PASS", run_live_smoke(args_for(paths, selection_sha), client=FakeClient())["blocking_reasons"])

    def test_cli_has_no_api_key_argument_and_manifest_redacts_credential(self):
        help_text = build_parser().format_help()
        self.assertNotIn("--api-key", help_text)
        with tempfile.TemporaryDirectory() as tmp, patched_env(GEMINI_API_KEY="dummy-secret"):
            paths, _manifest, selection_sha = write_fixture(tmp)
            result = run_live_smoke(args_for(paths, selection_sha), client=FakeClient())
            self.assertEqual(result["status"], "PASS")
            manifest_text = (paths["out"] / "pilot_300_v1_smoke_run_manifest.json").read_text()
            self.assertNotIn("dummy-secret", manifest_text)
            self.assertNotIn("REDACTED", json.dumps(result.get("items", [])))
            run_manifest = json.loads(manifest_text)
            self.assertTrue(run_manifest["credential_present"])
            self.assertFalse(run_manifest["credential_value_logged"])

    def test_holdout_excluded_and_selection_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            _paths, manifest, _selection_sha = write_fixture(tmp)
            first = select_smoke_samples(manifest, max_segments=5)
            second = select_smoke_samples(manifest, max_segments=5)
            self.assertEqual([item["stable_segment_key"] for item in first], [item["stable_segment_key"] for item in second])
            self.assertNotIn("seg-holdout", [item["stable_segment_key"] for item in first])

    def test_payload_reused_from_unsubmitted_jsonl_and_no_prompt_reassembly(self):
        with tempfile.TemporaryDirectory() as tmp, patched_env(GEMINI_API_KEY="dummy"):
            paths, _manifest, selection_sha = write_fixture(tmp)
            client = FakeClient()
            result = run_live_smoke(args_for(paths, selection_sha), client=client)
            self.assertEqual(result["status"], "PASS")
            jsonl_first = read_jsonl(paths["jsonl"])[0]["request"]["contents"][0]["parts"][0]["text"]
            self.assertEqual(client.calls[0]["payload"]["contents"][0]["parts"][0]["text"], jsonl_first)
            self.assertTrue(all(item["payload_source"] == "pilot_300_v1_batch_unsubmitted.jsonl" for item in result["items"]))
            self.assertTrue(all(item["prompt_reassembled"] is False for item in result["items"]))

    def test_success_non_json_and_schema_invalid_paths(self):
        with tempfile.TemporaryDirectory() as tmp, patched_env(GEMINI_API_KEY="dummy"):
            paths, _manifest, selection_sha = write_fixture(tmp)
            self.assertEqual(run_live_smoke(args_for(paths, selection_sha), client=FakeClient())["status"], "PASS")
        with tempfile.TemporaryDirectory() as tmp, patched_env(GEMINI_API_KEY="dummy"):
            paths, _manifest, selection_sha = write_fixture(tmp)
            response = success_response(candidates=[{"content": {"parts": [{"text": "not json"}]}}])
            result = run_live_smoke(args_for(paths, selection_sha, max_segments=3), client=FakeClient(responses=[response, success_response(), success_response()]))
            self.assertIn(result["status"], {"PARTIAL", "FAIL"})
            self.assertGreaterEqual(result["parse_failed_count"], 1)
        with tempfile.TemporaryDirectory() as tmp, patched_env(GEMINI_API_KEY="dummy"):
            paths, _manifest, selection_sha = write_fixture(tmp)
            result = run_live_smoke(args_for(paths, selection_sha, max_segments=3), client=FakeClient(responses=[schema_invalid_response(), success_response(), success_response()]))
            self.assertIn(result["status"], {"PARTIAL", "FAIL"})
            self.assertGreaterEqual(result["schema_invalid_count"], 1)

    def test_budget_cap_divergence_model_warnings_and_decimal_cost(self):
        with tempfile.TemporaryDirectory() as tmp, patched_env(GEMINI_API_KEY="dummy"):
            paths, _manifest, selection_sha = write_fixture(tmp)
            high_usage = success_response(
                modelVersion="models/other-pro",
                usageMetadata={
                    "promptTokenCount": 100000,
                    "candidatesTokenCount": 100000,
                    "thoughtsTokenCount": 100000,
                    "totalTokenCount": 300000,
                },
            )
            result = run_live_smoke(args_for(paths, selection_sha, max_segments=3, budget_usd="0.50"), client=FakeClient(responses=[high_usage, success_response(), success_response()]))
            self.assertIn("model_version_drift", result["warnings"])
            self.assertIn("cost_estimate_divergence_gt_2x", result["warnings"])
            self.assertIn(result["status"], {"PARTIAL", "FAIL"})
            self.assertEqual(decimal_ratio("100", "20"), __import__("decimal").Decimal("5.000"))

    def test_model_version_unavailable_warning(self):
        with tempfile.TemporaryDirectory() as tmp, patched_env(GEMINI_API_KEY="dummy"):
            paths, _manifest, selection_sha = write_fixture(tmp)
            response = success_response()
            response.pop("modelVersion")
            result = run_live_smoke(args_for(paths, selection_sha, max_segments=3), client=FakeClient(responses=[response, success_response(), success_response()]))
            self.assertIn("model_version_unavailable", result["warnings"])

    def test_retry_policy(self):
        with tempfile.TemporaryDirectory() as tmp, patched_env(GEMINI_API_KEY="dummy"):
            paths, _manifest, selection_sha = write_fixture(tmp)
            client = FakeClient(errors=[ProviderError(500, "temporary"), None, None, None])
            result = run_live_smoke(args_for(paths, selection_sha, max_segments=3), client=client, sleep_fn=lambda _seconds: None)
            self.assertEqual(result["items"][0]["attempts"], 2)
            self.assertEqual(result["status"], "PASS")
        with tempfile.TemporaryDirectory() as tmp, patched_env(GEMINI_API_KEY="dummy"):
            paths, _manifest, selection_sha = write_fixture(tmp)
            client = FakeClient(errors=[ProviderError(401, "auth")])
            result = run_live_smoke(args_for(paths, selection_sha, max_segments=3), client=client, sleep_fn=lambda _seconds: None)
            self.assertEqual(result["items"][0]["attempts"], 1)
            self.assertIn(result["status"], {"PARTIAL", "FAIL"})

    def test_result_quality_signal_false_and_no_tuning_artifact(self):
        with tempfile.TemporaryDirectory() as tmp, patched_env(GEMINI_API_KEY="dummy"):
            paths, _manifest, selection_sha = write_fixture(tmp)
            result = run_live_smoke(args_for(paths, selection_sha), client=FakeClient())
            self.assertFalse(result["quality_signal"])
            self.assertTrue(all(item["quality_signal"] is False for item in result["items"]))
            self.assertFalse(result["batch_submission_allowed_now"])
            self.assertFalse(any("glossary" in str(path).lower() and "update" in str(path).lower() for path in paths["out"].iterdir()))


if __name__ == "__main__":
    unittest.main()
