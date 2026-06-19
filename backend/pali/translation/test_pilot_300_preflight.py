import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from backend.pali.scripts.build_pilot_300_manifest import selection_content_sha256
from backend.pali.scripts.run_pilot_300_preflight import (
    PILOT75_TOTALS,
    PreflightBlocked,
    PriceProfile,
    TokenEstimate,
    build_unsubmitted_jsonl,
    estimate_pilot_300_cost,
    pricing_self_check,
    run_budget_guardrail_test,
    run_preflight,
    source_integrity_precheck,
    verify_manifest_identity,
)
from backend.pali.translation.budget import estimate_request_cost


ROOT = Path(__file__).resolve().parents[3]


def source_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def synthetic_inventory_and_manifest():
    inventory = []
    manifest_items = []
    for index in range(300):
        key = f"seg-{index:04d}"
        text = f"katamo dhammo lakkhaṇa rasa source text {index}"
        text_layer = ("mula", "atthakatha", "tika")[index % 3]
        length_bucket = ("short", "medium", "long")[index % 3]
        chunk_type = "verse" if index % 5 == 0 else "prose"
        if index < 5:
            selection_bucket = "heading_title_probe"
            selection_group = "representative"
        elif index < 100:
            selection_bucket = "abhidhamma_definition"
            selection_group = "hard"
        else:
            selection_bucket = "representative_stratified"
            selection_group = "representative"
        item_hash = source_hash(text)
        inventory.append(
            {
                "stable_segment_key": key,
                "source_text_hash": item_hash,
                "source_path": f"romn/s{index:04d}.xml",
                "original_text": text,
                "normalized_text": text,
                "text_layer": text_layer,
                "length_bucket": length_bucket,
                "chunk_type": chunk_type,
                "pitaka": "sutta",
                "nikaya": "TestNikaya",
                "heading_path": [{"text": "Test", "type": "title", "level": 2}],
            }
        )
        manifest_items.append(
            {
                "stable_segment_key": key,
                "source_text_hash": item_hash,
                "source_path": f"romn/s{index:04d}.xml",
                "text_layer": text_layer,
                "length_bucket": length_bucket,
                "chunk_type": chunk_type,
                "selection_group": selection_group,
                "selection_bucket": selection_bucket,
                "selection_reason": "test",
                "secondary_tags": [],
                "gold_candidate": index < 20,
                "pool_candidate": "holdout_gold" if index < 20 else None,
                "pitaka": "sutta",
                "nikaya": "TestNikaya",
                "heading_path": [{"text": "Test", "type": "title", "level": 2}],
            }
        )
    manifest = {
        "schema_version": "pali_pilot_300_manifest_v1",
        "run_id": "pilot_300_v1",
        "selection_seed": "pilot_300_v1",
        "source_provenance": {
            "source_commit": "test-commit",
            "inventory_sha256": "",
            "source_path_root": "data/tipitaka-xml",
        },
        "summary": {
            "selected_count": 300,
            "hard_count": 100,
            "representative_count": 200,
            "by_source_path_prefix": {"s": 300},
        },
        "items": manifest_items,
    }
    return inventory, manifest


def synthetic_pilot75():
    items = []
    for index in range(75):
        items.append(
            {
                "stable_segment_key": f"pilot75-{index}",
                "source_text_hash": f"h-{index}",
                "text_layer": ("mula", "atthakatha", "tika")[index % 3],
                "length_bucket": ("short", "medium", "long")[index % 3],
                "chunk_type": "verse" if index % 5 == 0 else "prose",
                "source_path": f"romn/p{index}.xml",
                "original_text": f"pilot seventy five text {index} dhamma",
                "prompt_token_count": 3000 + index,
                "candidates_token_count": 500 + index,
                "thoughts_token_count": 1000 + index,
                "total_token_count": 4500 + index,
                "actual_cost_usd": "0.01",
                "status": "succeeded",
                "schema_valid": True,
            }
        )
    return {"items": items}


def write_fixture(tmp):
    inventory, manifest = synthetic_inventory_and_manifest()
    inventory_path = Path(tmp) / "inventory.json"
    inventory_path.write_text(json.dumps({"items": inventory}, ensure_ascii=False), encoding="utf-8")
    inventory_sha = hashlib.sha256(inventory_path.read_bytes()).hexdigest()
    manifest["source_provenance"]["inventory_sha256"] = inventory_sha
    selection_sha = selection_content_sha256(manifest)
    validation = {
        "valid": True,
        "checks": {
            "selection_content_hash": {"sha256": selection_sha},
            "inventory_hash_present": {"sha256": inventory_sha},
        },
    }
    manifest_path = Path(tmp) / "manifest.json"
    validation_path = Path(tmp) / "validation.json"
    pilot75_path = Path(tmp) / "pilot75.json"
    glossary_path = Path(tmp) / "glossary.json"
    gold_path = Path(tmp) / "gold.json"
    prompt_calibration_path = Path(tmp) / "missing_prompt_calibration.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    validation_path.write_text(json.dumps(validation, ensure_ascii=False), encoding="utf-8")
    pilot75_path.write_text(json.dumps(synthetic_pilot75(), ensure_ascii=False), encoding="utf-8")
    glossary_path.write_text("{}", encoding="utf-8")
    gold_path.write_text(json.dumps({"schema_version": "test", "entries": []}), encoding="utf-8")
    return {
        "inventory": inventory,
        "manifest": manifest,
        "selection_sha": selection_sha,
        "paths": {
            "inventory": inventory_path,
            "manifest": manifest_path,
            "validation": validation_path,
            "pilot75": pilot75_path,
            "glossary": glossary_path,
            "gold": gold_path,
            "prompt_calibration": prompt_calibration_path,
        },
    }


def args_for(tmp):
    fixture = write_fixture(tmp)
    paths = fixture["paths"]
    return fixture, argparse.Namespace(
        manifest=str(paths["manifest"]),
        validation=str(paths["validation"]),
        inventory=str(paths["inventory"]),
        pilot75_parsed=str(paths["pilot75"]),
        glossary=str(paths["glossary"]),
        out=str(Path(tmp) / "out"),
        qa_dryrun_out=str(Path(tmp) / "qa"),
        expected_selection_sha=fixture["selection_sha"],
        budget_usd="20",
        prompt_calibration=str(paths["prompt_calibration"]),
        gold=str(paths["gold"]),
        pretty=True,
    )


class Pilot300PreflightTests(unittest.TestCase):
    def test_pricing_self_check_reproduces_75_actual_cost(self):
        profile = PriceProfile(
            input_usd_per_million_tokens=__import__("decimal").Decimal("1.0"),
            output_usd_per_million_tokens=__import__("decimal").Decimal("6.0"),
            thinking_usd_per_million_tokens=__import__("decimal").Decimal("6.0"),
        )
        result = pricing_self_check(profile)
        self.assertTrue(result["pass"])
        self.assertEqual(result["recomputed_cost_usd"], str(PILOT75_TOTALS["actual_cost_usd"]))
        cost = estimate_request_cost(
            TokenEstimate(PILOT75_TOTALS["input_tokens"], PILOT75_TOTALS["output_tokens"], PILOT75_TOTALS["thinking_tokens"]),
            profile,
        )
        self.assertEqual(str(cost), "1.433777")

    def test_expected_selection_hash_mismatch_blocks(self):
        fixture = synthetic_inventory_and_manifest()
        _inventory, manifest = fixture
        validation = {"valid": True, "checks": {"selection_content_hash": {"sha256": selection_content_sha256(manifest)}}}
        with self.assertRaises(PreflightBlocked) as ctx:
            verify_manifest_identity(manifest, validation, expected_selection_sha="wrong")
        self.assertEqual(ctx.exception.status, "BLOCKED_HASH_MISMATCH")

    def test_cost_estimate_and_jsonl_source_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture, _args = args_for(tmp)
            identity = verify_manifest_identity(fixture["manifest"], json.loads(fixture["paths"]["validation"].read_text()), expected_selection_sha=fixture["selection_sha"])
            identity["manifest_path"] = str(fixture["paths"]["manifest"])
            report = estimate_pilot_300_cost(
                manifest=fixture["manifest"],
                inventory_items=fixture["inventory"],
                pilot75=synthetic_pilot75(),
                price_profile=PriceProfile(
                    input_usd_per_million_tokens=__import__("decimal").Decimal("1.0"),
                    output_usd_per_million_tokens=__import__("decimal").Decimal("6.0"),
                    thinking_usd_per_million_tokens=__import__("decimal").Decimal("6.0"),
                ),
                prompt_calibration_path=fixture["paths"]["prompt_calibration"],
                budget_usd=__import__("decimal").Decimal("20"),
                identity=identity,
            )
            self.assertEqual(report["special_slices"]["heading_title_probe"]["count"], 5)
            self.assertGreater(float(report["estimate_totals"]["planning_p90"]["official_cost_usd"]), 0)
            jsonl = build_unsubmitted_jsonl(
                manifest=fixture["manifest"],
                inventory_items=fixture["inventory"],
                estimate=report,
                jsonl_path=Path(tmp) / "out.jsonl",
                jsonl_manifest_path=Path(tmp) / "manifest.json",
                pretty=True,
            )
            self.assertTrue(jsonl["validation"]["valid"])
            self.assertFalse(jsonl["manifest"]["submitted"])
            integrity = source_integrity_precheck(
                manifest=fixture["manifest"],
                inventory_items=fixture["inventory"],
                jsonl_manifest=jsonl["manifest"],
            )
            self.assertTrue(integrity["valid"])

    def test_source_integrity_mismatch_blocks_precheck(self):
        inventory, manifest = synthetic_inventory_and_manifest()
        sidecar = {
            "items": [
                {"stable_segment_key": item["stable_segment_key"], "jsonl_source_text_hash": item["source_text_hash"]}
                for item in manifest["items"]
            ]
        }
        sidecar["items"][0]["jsonl_source_text_hash"] = "wrong"
        integrity = source_integrity_precheck(manifest=manifest, inventory_items=inventory, jsonl_manifest=sidecar)
        self.assertFalse(integrity["valid"])
        self.assertFalse(integrity["manifest_to_jsonl_hash_match"])

    def test_budget_guardrail_blocks_over_budget_but_never_allows_submission(self):
        result = run_budget_guardrail_test(
            budget_usd=__import__("decimal").Decimal("20"),
            conservative_gate_cost_usd=__import__("decimal").Decimal("1"),
        )
        self.assertTrue(result["valid"])
        self.assertFalse(result["actual_gate"]["batch_submission_allowed_now"])
        self.assertFalse(result["synthetic_over_budget"]["can_submit"])

    def test_full_preflight_generates_outputs_and_mock_qa(self):
        with tempfile.TemporaryDirectory() as tmp:
            _fixture, args = args_for(tmp)
            result = run_preflight(args)
            self.assertEqual(result["readiness_status"], "PASS_READY_FOR_USER_APPROVAL")
            self.assertTrue((Path(args.out) / "pilot_300_v1_cost_estimate.json").exists())
            self.assertTrue((Path(args.out) / "pilot_300_v1_batch_unsubmitted.jsonl").exists())
            self.assertTrue((Path(args.out) / "pilot_300_v1_source_integrity_precheck.json").exists())
            self.assertTrue((Path(args.qa_dryrun_out) / "review_report.md").exists())
            report = (Path(args.qa_dryrun_out) / "review_report.md").read_text(encoding="utf-8")
            self.assertIn("mock QA dry-run is not a translation quality signal", report)
            self.assertIn("gold empty is expected", report)

    def test_cross_pythonhashseed_selection_output_is_same(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = write_fixture(tmp)
            paths = fixture["paths"]
            base_cmd = [
                sys.executable,
                "-m",
                "backend.pali.scripts.run_pilot_300_preflight",
                "--manifest",
                str(paths["manifest"]),
                "--validation",
                str(paths["validation"]),
                "--inventory",
                str(paths["inventory"]),
                "--pilot75-parsed",
                str(paths["pilot75"]),
                "--glossary",
                str(paths["glossary"]),
                "--expected-selection-sha",
                fixture["selection_sha"],
                "--budget-usd",
                "20",
                "--prompt-calibration",
                str(paths["prompt_calibration"]),
                "--gold",
                str(paths["gold"]),
            ]
            env1 = dict(os.environ, PYTHONHASHSEED="1")
            env2 = dict(os.environ, PYTHONHASHSEED="999")
            out1 = Path(tmp) / "out1"
            qa1 = Path(tmp) / "qa1"
            out2 = Path(tmp) / "out2"
            qa2 = Path(tmp) / "qa2"
            subprocess.run(base_cmd + ["--out", str(out1), "--qa-dryrun-out", str(qa1)], cwd=ROOT, env=env1, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            subprocess.run(base_cmd + ["--out", str(out2), "--qa-dryrun-out", str(qa2)], cwd=ROOT, env=env2, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            r1 = json.loads((out1 / "pilot_300_v1_batch_readiness.json").read_text())
            r2 = json.loads((out2 / "pilot_300_v1_batch_readiness.json").read_text())
            self.assertEqual(r1["selection_content_sha256"], r2["selection_content_sha256"])
            self.assertEqual(r1["estimated_cost_usd_conservative_gate"], r2["estimated_cost_usd_conservative_gate"])


if __name__ == "__main__":
    unittest.main()
