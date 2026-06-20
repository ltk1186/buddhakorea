import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.pali.scripts.generate_qa_report import generate_report
from backend.pali.scripts.run_pilot_300_batch import run as run_batch
from backend.pali.translation.pali_qa_findings_classifier import classify_review_findings
from backend.pali.translation.test_pilot_300_batch import args_for as batch_args_for
from backend.pali.translation.test_pilot_300_batch import write_fixture


def parsed_item(
    key="seg-001",
    *,
    natural="역관(paṭiloma)은 반대 방향이라는 뜻이다.",
    local_flags=None,
    quality_flags=None,
):
    return {
        "stable_segment_key": key,
        "source_path": "romn/s0501a.att.xml",
        "text_layer": "atthakatha",
        "chunk_type": "prose",
        "length_bucket": "medium",
        "original_text": "paṭiloma",
        "source_text_hash": f"hash-{key}",
        "schema_valid": True,
        "status": "succeeded",
        "literal_ko": natural,
        "natural_ko": natural,
        "terms": [],
        "grammar_notes": [],
        "doctrinal_notes": [],
        "uncertainties": [],
        "quality_flags": [] if quality_flags is None else quality_flags,
        "local_validator_flags": ["contains_untranslated_pali"] if local_flags is None else local_flags,
    }


def write_inputs(root: Path, parsed_payload: dict):
    parsed = root / "parsed.json"
    gold = root / "gold.json"
    glossary_qa = root / "glossary_qa.json"
    parsed.write_text(json.dumps(parsed_payload, ensure_ascii=False), encoding="utf-8")
    gold.write_text(json.dumps({"schema_version": "test_gold", "entries": []}), encoding="utf-8")
    glossary_qa.write_text(json.dumps({"schema_version": "test_glossary_qa"}), encoding="utf-8")
    return parsed, gold, glossary_qa


def report_args(root: Path, parsed: Path, gold: Path, glossary_qa: Path, *, classifier="on"):
    return argparse.Namespace(
        parsed=str(parsed),
        before_parsed=None,
        gold=str(gold),
        glossary_qa=str(glossary_qa),
        reference_registry=None,
        out=str(root / "qa_out"),
        sample_config=None,
        sample_seed=None,
        pali_findings_classifier=classifier,
    )


def comparable_findings(payload: dict):
    return {
        "summary_after": payload["summary_after"],
        "subsignal_counts": payload["subsignal_counts"],
        "run_coverage_summary": payload["run_coverage_summary"],
        "sampling_recommendation": payload["sampling_recommendation"],
        "items": [
            {
                "stable_segment_key": item["stable_segment_key"],
                "signals_after": item["signals_after"],
                "decision": item["decision"],
                "review_required_after_classification": item["review_required_after_classification"],
                "pali_runs": item["pali_runs"],
                "uncovered_pali_runs": item["uncovered_pali_runs"],
                "run_worst_case_passed": item["run_worst_case_passed"],
                "signal_worst_case_passed": item["signal_worst_case_passed"],
            }
            for item in payload["items"]
        ],
    }


class QaReportClassifierIntegrationTests(unittest.TestCase):
    def test_classifier_on_creates_outputs_and_manifest_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parsed, gold, glossary_qa = write_inputs(root, {"items": [parsed_item()]})
            result = generate_report(report_args(root, parsed, gold, glossary_qa, classifier="on"))
            out = Path(result["out"])
            for name in (
                "findings.json",
                "findings.md",
                "review_queue_reclassified.json",
                "pali_qa_pattern_decisions_v1.json",
            ):
                self.assertTrue((out / name).exists())
            report = (out / "review_report.md").read_text(encoding="utf-8")
            self.assertIn("Pāli Findings Classifier Summary", report)
            self.assertIn("Priority counts", report)
            manifest = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
            section = manifest["pali_findings_classifier"]
            self.assertTrue(section["enabled"])
            self.assertEqual(section["api_network_calls"], 0)
            self.assertEqual(manifest["qa_summary"]["raw_human_needed"], 1)
            self.assertEqual(manifest["qa_summary"]["effective_human_needed"], 0)

    def test_integrated_output_equals_standalone_classifier_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parsed_payload = {
                "items": [
                    parsed_item("allowed", natural="역관(paṭiloma)은 설명이다."),
                    parsed_item(
                        "grammar",
                        natural="역관(paṭiloma)은 설명이다.",
                        quality_flags=["grammar_uncertain"],
                        local_flags=["contains_untranslated_pali"],
                    ),
                    parsed_item("strict", natural="이 문장은 anattā를 그대로 남긴다."),
                ]
            }
            parsed, gold, glossary_qa = write_inputs(root, parsed_payload)
            result = generate_report(report_args(root, parsed, gold, glossary_qa, classifier="on"))
            out = Path(result["out"])
            integrated = json.loads((out / "findings.json").read_text(encoding="utf-8"))
            raw_queue = json.loads((out / "review_queue.json").read_text(encoding="utf-8"))
            manifest = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
            standalone = classify_review_findings(
                review_queue=raw_queue,
                parsed_payload=parsed_payload,
                review_report_path=str(out / "review_report.md"),
                review_queue_path=str(out / "review_queue.json"),
                parsed_path=str(parsed),
                sample_seed=manifest["sample_seed"],
            )
            self.assertEqual(comparable_findings(integrated), comparable_findings(standalone))

    def test_classifier_off_keeps_effective_human_needed_equal_to_raw(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parsed, gold, glossary_qa = write_inputs(root, {"items": [parsed_item()]})
            generate_report(report_args(root, parsed, gold, glossary_qa, classifier="off"))
            manifest = json.loads((root / "qa_out" / "run_manifest.json").read_text(encoding="utf-8"))
            section = manifest["pali_findings_classifier"]
            self.assertFalse(section["enabled"])
            self.assertEqual(section["mode"], "off")
            self.assertEqual(section["effective_human_needed"], section["raw_human_needed"])
            self.assertEqual(manifest["qa_summary"]["effective_human_needed"], manifest["qa_summary"]["raw_human_needed"])

    def test_classifier_auto_skip_keeps_effective_human_needed_equal_to_raw(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {"items": [parsed_item(local_flags=[], quality_flags=["low_confidence"], natural="일반 문장")]}
            parsed, gold, glossary_qa = write_inputs(root, payload)
            generate_report(report_args(root, parsed, gold, glossary_qa, classifier="auto"))
            manifest = json.loads((root / "qa_out" / "run_manifest.json").read_text(encoding="utf-8"))
            section = manifest["pali_findings_classifier"]
            self.assertFalse(section["enabled"])
            self.assertEqual(section["skip_reason"], "no_contains_untranslated_pali_or_grammar_uncertain_signals")
            self.assertEqual(section["effective_human_needed"], section["raw_human_needed"])

    def test_classifier_metadata_records_caveat_and_pattern_decisions_output_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parsed, gold, glossary_qa = write_inputs(root, {"items": [parsed_item()]})
            generate_report(report_args(root, parsed, gold, glossary_qa, classifier="on"))
            out = root / "qa_out"
            findings = json.loads((out / "findings.json").read_text(encoding="utf-8"))
            decisions = json.loads((out / "pali_qa_pattern_decisions_v1.json").read_text(encoding="utf-8"))
            self.assertIn("correctness_caveat", findings)
            self.assertIn("not certified-correct translations", findings["correctness_caveat"])
            self.assertEqual(decisions["record_type"], "output_record_not_config")
            self.assertFalse(decisions["configurable"])

    def test_review_queue_raw_is_not_replaced_by_reclassified_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parsed, gold, glossary_qa = write_inputs(root, {"items": [parsed_item()]})
            generate_report(report_args(root, parsed, gold, glossary_qa, classifier="on"))
            out = root / "qa_out"
            raw_queue = json.loads((out / "review_queue.json").read_text(encoding="utf-8"))
            reclassified = json.loads((out / "review_queue_reclassified.json").read_text(encoding="utf-8"))
            self.assertEqual(raw_queue["schema_version"], "pali_review_queue_v1_2")
            self.assertEqual(reclassified["schema_version"], "pali_review_queue_reclassified_v1")
            self.assertNotIn("decision", raw_queue["items"][0])
            self.assertIn("decision", reclassified["items"][0])

    def test_run_pilot_300_batch_qa_passes_classifier_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, selection_sha = write_fixture(tmp)
            paths["out"].mkdir(parents=True)
            (paths["out"] / "pilot_300_batch_parsed.json").write_text(json.dumps({"items": []}), encoding="utf-8")
            with patch("backend.pali.scripts.run_pilot_300_batch.subprocess.run") as mocked:
                mocked.return_value.returncode = 0
                mocked.return_value.stdout = "ok"
                mocked.return_value.stderr = ""
                result = run_batch(
                    batch_args_for(paths, mode="qa", selection_sha=selection_sha, pali_findings_classifier="off")
                )
            self.assertEqual(result["status"], "QA_COMPLETE")
            command = mocked.call_args.args[0]
            self.assertIn("--pali-findings-classifier", command)
            self.assertIn("off", command)


if __name__ == "__main__":
    unittest.main()
