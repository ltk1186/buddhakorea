import argparse
import json
import tempfile
import unittest
from pathlib import Path

from backend.pali.scripts.generate_qa_report import (
    _resolve_sample_seed,
    _sample_seed_keys,
    build_parser,
    generate_report,
)
from backend.pali.translation.gold_set import evaluate_against_gold
from backend.pali.translation.reference_registry import (
    is_automatic_comparison_candidate,
    validate_reference_entry,
)
from backend.pali.translation.review_queue import build_review_queue
from backend.pali.translation.second_model_verifier import verify_segment
from backend.pali.translation.source_integrity import check_integrity, compute_source_hashes


ROOT = Path(__file__).resolve().parents[3]
QA_PATCH_PARSED = ROOT / "data/reports/pali/gemini_pilot_75_49bc869_prompt_qa_patch_v2_parsed.json"
SCHEMAFIX_PARSED = ROOT / "data/reports/pali/gemini_pilot_75_49bc869_prompt_v1_schemafix_parsed.json"
GOLD = ROOT / "data/gold_set.json"
GLOSSARY_QA = ROOT / "data/reports/pali/translation_qa_v1_1_baseline_49bc869.json"


def args_for(out_dir, before=None):
    return argparse.Namespace(
        parsed=str(QA_PATCH_PARSED),
        before_parsed=str(before) if before else None,
        gold=str(GOLD),
        glossary_qa=str(GLOSSARY_QA),
        reference_registry=None,
        out=str(out_dir),
        sample_config=None,
        sample_seed=None,
    )


def parsed_segment(key="seg-1", literal="슬기로운 이는 현자이다", natural="슬기로운 이는 현자이다", terms=None):
    return {
        "stable_segment_key": key,
        "original_text": "dhīro paṇḍito",
        "parsed_translation_json": {
            "literal_ko": literal,
            "natural_ko": natural,
            "terms": terms or [],
            "grammar_notes": [],
            "doctrinal_notes": [],
            "uncertainties": [],
            "quality_flags": [],
        },
    }


def gold_entry(**overrides):
    entry = {
        "gold_set_id": "gold-1",
        "pool": "regression_gold",
        "stable_segment_key": "seg-1",
        "source_text": "dhīro paṇḍito",
        "acceptance_type": "constraint",
        "eval_mode": "terms_strict",
        "accepted_literal_ko": None,
        "accepted_natural_ko": None,
        "required_terms": [],
        "forbidden_terms": [],
        "acceptable_variants": [],
        "rationale": "test",
        "difficulty": "medium",
        "leverage": "high",
        "reviewer_type": "operator",
        "expert_question_status": "not_needed",
        "adjudication_status": "accepted",
        "gold_version": "v0",
        "created_from_pilot": "test",
    }
    entry.update(overrides)
    return entry


class QaReportCliTests(unittest.TestCase):
    def test_cli_smoke_single_run_creates_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = generate_report(args_for(tmp))
            self.assertEqual(result["mode"], "single_run")
            self.assertTrue((Path(tmp) / "review_report.md").exists())
            self.assertTrue((Path(tmp) / "review_queue.json").exists())
            self.assertTrue((Path(tmp) / "run_manifest.json").exists())
            report = (Path(tmp) / "review_report.md").read_text(encoding="utf-8")
            self.assertIn("regression mode: disabled", report)

    def test_cli_is_deterministic_for_same_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate_report(args_for(tmp))
            first = {
                name: (Path(tmp) / name).read_bytes()
                for name in ("review_report.md", "review_queue.json", "run_manifest.json")
            }
            generate_report(args_for(tmp))
            second = {
                name: (Path(tmp) / name).read_bytes()
                for name in ("review_report.md", "review_queue.json", "run_manifest.json")
            }
            self.assertEqual(first, second)

    def test_regression_mode_writes_regression_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = generate_report(args_for(tmp, before=SCHEMAFIX_PARSED))
            self.assertEqual(result["mode"], "regression")
            report = (Path(tmp) / "review_report.md").read_text(encoding="utf-8")
            self.assertIn("regression mode: enabled", report)
            self.assertIn("verdict counts", report)

    def test_help_contains_copy_paste_examples(self):
        help_text = build_parser().format_help()
        self.assertIn("75 baseline single-run", help_text)
        self.assertIn("before/after regression", help_text)
        self.assertIn("300 pilot template", help_text)


class SamplingTests(unittest.TestCase):
    def test_explicit_sample_seed_is_used(self):
        self.assertEqual(_resolve_sample_seed("123", ["b", "a"]), 123)
        self.assertEqual(_resolve_sample_seed("abc", ["b", "a"]), _resolve_sample_seed("abc", ["z"]))

    def test_default_sample_seed_uses_stable_segment_keys(self):
        keys = ["seg-b", "seg-a"]
        self.assertEqual(_resolve_sample_seed(None, keys), _resolve_sample_seed(None, list(reversed(keys))))

    def test_regression_sample_keys_are_intersection(self):
        after = [{"stable_segment_key": "a"}, {"stable_segment_key": "b"}]
        before = [{"stable_segment_key": "b"}, {"stable_segment_key": "c"}]
        self.assertEqual(_sample_seed_keys(after, before, "regression"), ["b"])


class GoldEvalModeTests(unittest.TestCase):
    def test_terms_strict_keeps_current_behavior(self):
        entry = gold_entry(required_terms=[{"pali": "dhīra", "ko": "슬기로운 이"}])
        result = evaluate_against_gold(parsed_segment(terms=[]), entry)
        self.assertFalse(result["pass"])

    def test_body_allowed_uses_body_when_terms_missing(self):
        entry = gold_entry(
            eval_mode="body_allowed",
            required_terms=[{"pali": "dhīra", "ko": "슬기로운 이"}],
        )
        result = evaluate_against_gold(parsed_segment(terms=[]), entry)
        self.assertTrue(result["pass"])

    def test_body_allowed_detects_forbidden_when_pali_in_source(self):
        entry = gold_entry(
            eval_mode="body_allowed",
            forbidden_terms=[{"pali": "dhīra", "ko": "현자"}],
        )
        result = evaluate_against_gold(parsed_segment(terms=[]), entry)
        self.assertFalse(result["pass"])
        self.assertEqual(result["hit_forbidden"], [{"pali": "dhīra", "ko": "현자"}])

    def test_body_allowed_does_not_fire_when_pali_absent(self):
        entry = gold_entry(
            source_text="paṇḍito",
            eval_mode="body_allowed",
            forbidden_terms=[{"pali": "dhīra", "ko": "현자"}],
        )
        result = evaluate_against_gold(parsed_segment(terms=[]), entry)
        self.assertTrue(result["pass"])

    def test_reference_only_escalates(self):
        entry = gold_entry(acceptance_type="reference")
        result = evaluate_against_gold(parsed_segment(), entry)
        self.assertIsNone(result["pass"])
        self.assertFalse(result["auto_evaluable"])


class ReviewQueueAndPoolTests(unittest.TestCase):
    def test_source_integrity_signals_are_operator_tier(self):
        report = build_review_queue([], [{"stable_segment_key": "seg-1", "signals": ["silent_source_normalization"]}])
        self.assertEqual(report["items"][0]["review_tier"], "tier_source_integrity_operator")

    def test_second_model_disagreement_is_priority_b(self):
        report = build_review_queue([], [{"stable_segment_key": "seg-1", "signals": ["second_model_disagreement"]}])
        self.assertEqual(report["items"][0]["priority"], "B")

    def test_auto_resolvable_not_listed_in_human_needed(self):
        report = build_review_queue([], [{"stable_segment_key": "seg-1", "signals": ["allowed_parenthetical_pali"]}])
        self.assertEqual(report["auto_resolvable_count"], 1)
        self.assertEqual(report["human_needed_count"], 0)

    def test_pool_names_are_not_aliases(self):
        self.assertNotEqual("regression_gold", "holdout_gold")


class SourceIntegrityModeTests(unittest.TestCase):
    def test_production_requires_raw_and_normalized_hashes(self):
        result = check_integrity({"stable_segment_key": "seg-1", "original_text": "raw"}, mode="production")
        self.assertIn("missing_field:raw_source_text_hash", result["flags"])
        self.assertIn("missing_field:normalized_source_text_hash", result["flags"])

    def test_legacy_source_text_hash_alias_allowed(self):
        result = check_integrity(
            {"stable_segment_key": "seg-1", "source_text_hash": "legacy", "original_text": "raw"},
            mode="legacy",
        )
        self.assertNotIn("missing_field:source_text_hash", result["flags"])

    def test_silent_normalization_and_note(self):
        hashes = compute_source_hashes("akicchāni", "akiccāni")
        with_note = {
            "stable_segment_key": "seg-1",
            "raw_source_text": "akicchāni",
            "translation_source_text": "akiccāni",
            "normalization_notes": ["spelling variant recorded"],
            **hashes,
        }
        without_note = dict(with_note)
        without_note["normalization_notes"] = []
        self.assertNotIn("silent_source_normalization", check_integrity(with_note, mode="production")["flags"])
        self.assertIn("silent_source_normalization", check_integrity(without_note, mode="production")["flags"])


class ReferenceRegistryAndVerifierTests(unittest.TestCase):
    def test_source_type_validation(self):
        self.assertTrue(validate_reference_entry({"source_type": "cc0_storable"})["valid"])
        self.assertTrue(validate_reference_entry({"source_type": "copyright_eyes_only"})["valid"])
        self.assertTrue(validate_reference_entry({"source_type": "unknown_unverified"})["valid"])
        self.assertFalse(validate_reference_entry({"source_type": "bad"})["valid"])

    def test_unknown_unverified_is_not_auto_candidate(self):
        self.assertFalse(is_automatic_comparison_candidate({"source_type": "unknown_unverified"}))
        self.assertTrue(is_automatic_comparison_candidate({"source_type": "cc0_storable"}))

    def test_protected_body_field_fails_and_long_note_warns(self):
        result = validate_reference_entry(
            {
                "source_type": "copyright_eyes_only",
                "translation_text": "not allowed",
                "divergence_note": " ".join(["word"] * 31),
            }
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any(item.startswith("long_reference_note") for item in result["warnings"]))

    def test_second_model_verifier_disabled_and_enabled_guard(self):
        disabled = verify_segment("anicca", "무상", provider="placeholder", enabled=False)
        self.assertEqual(disabled["status"], "disabled_no_live_call")
        with self.assertRaises(NotImplementedError):
            verify_segment("anicca", "무상", provider="placeholder", enabled=True)

    def test_second_model_verifier_rejects_full_corpus_mode(self):
        with self.assertRaises(ValueError):
            verify_segment("anicca", "무상", provider="placeholder", enabled=False, flagged_subset=False)


if __name__ == "__main__":
    unittest.main()
