import unittest

from backend.pali.translation.gold_set import (
    evaluate_against_gold,
    gold_anchored_verdict,
    validate_gold_entry,
)
from backend.pali.translation.reference_registry import (
    flag_reference_divergence,
    validate_reference_entry,
)
from backend.pali.translation.review_queue import build_review_queue
from backend.pali.translation.source_integrity import (
    check_integrity,
    compute_source_hashes,
    detect_silent_normalization,
)


def parsed_segment(key="seg-1", literal="직역", natural="자연역", terms=None, **extra):
    data = {
        "stable_segment_key": key,
        "schema_valid": True,
        "status": "succeeded",
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
    data.update(extra)
    return data


def gold_entry(**overrides):
    entry = {
        "gold_set_id": "gold-1",
        "pool": "regression_gold",
        "stable_segment_key": "seg-1",
        "source_text": "khandhānaṃ",
        "acceptance_type": "constraint",
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


class GoldSetTests(unittest.TestCase):
    def test_exact_evaluation_passes(self):
        entry = gold_entry(
            acceptance_type="exact",
            accepted_literal_ko="직역",
            accepted_natural_ko="자연역",
        )
        result = evaluate_against_gold(parsed_segment(), entry)
        self.assertTrue(result["pass"])
        self.assertTrue(result["auto_evaluable"])

    def test_constraint_required_terms_pass(self):
        entry = gold_entry(required_terms=[{"pali": "khandha", "ko": "무더기"}])
        segment = parsed_segment(terms=[{"pali": "khandha", "ko": "무더기"}])
        result = evaluate_against_gold(segment, entry)
        self.assertTrue(result["pass"])
        self.assertEqual(result["matched_required"], [{"pali": "khandha", "ko": "무더기"}])

    def test_constraint_forbidden_terms_fail(self):
        entry = gold_entry(forbidden_terms=[{"pali": "khandha", "ko": "무리"}])
        segment = parsed_segment(terms=[{"pali": "khandha", "ko": "무리"}])
        result = evaluate_against_gold(segment, entry)
        self.assertFalse(result["pass"])
        self.assertEqual(result["hit_forbidden"], [{"pali": "khandha", "ko": "무리"}])

    def test_reference_only_is_not_auto_evaluable(self):
        entry = gold_entry(acceptance_type="reference")
        result = evaluate_against_gold(parsed_segment(), entry)
        self.assertIsNone(result["pass"])
        self.assertFalse(result["auto_evaluable"])

    def test_gold_anchored_verdict_improved(self):
        entry = gold_entry(required_terms=[{"pali": "khandha", "ko": "무더기"}])
        before = parsed_segment(terms=[{"pali": "khandha", "ko": "무리"}])
        after = parsed_segment(terms=[{"pali": "khandha", "ko": "무더기"}])
        result = gold_anchored_verdict(before, after, entry)
        self.assertEqual(result["verdict"], "improved")

    def test_gold_anchored_verdict_worsened(self):
        entry = gold_entry(required_terms=[{"pali": "khandha", "ko": "무더기"}])
        before = parsed_segment(terms=[{"pali": "khandha", "ko": "무더기"}])
        after = parsed_segment(terms=[{"pali": "khandha", "ko": "무리"}])
        result = gold_anchored_verdict(before, after, entry)
        self.assertEqual(result["verdict"], "worsened")

    def test_missing_gold_escalates(self):
        result = gold_anchored_verdict(parsed_segment(), parsed_segment(), None)
        self.assertEqual(result["verdict"], "escalate")

    def test_protected_external_translation_text_is_rejected(self):
        entry = gold_entry(
            external_references=[
                {"edition": "example", "ref_locator": "DN 1", "external_translation_text": "not allowed"}
            ]
        )
        result = validate_gold_entry(entry)
        self.assertFalse(result["valid"])


class ReviewQueueTests(unittest.TestCase):
    def test_deduplicates_same_group(self):
        qa_items = [
            {"stable_segment_key": f"seg-{i}", "signals": ["citation_mapping_missing"], "dedup_group": "citation:dn"}
            for i in range(80)
        ]
        report = build_review_queue([], qa_items)
        self.assertEqual(report["deduped_item_count"], 1)
        self.assertEqual(report["items"][0]["recurrence_count"], 80)

    def test_auto_resolvable_and_human_needed_are_separated(self):
        qa_items = [
            {"stable_segment_key": "seg-1", "signals": ["citation_mapping_missing"], "dedup_group": "citation:dn"},
            {"stable_segment_key": "seg-2", "signals": ["gold_regression_worsened"], "dedup_group": "gold:1"},
        ]
        report = build_review_queue([], qa_items)
        self.assertEqual(report["auto_resolvable_count"], 1)
        self.assertEqual(report["human_needed_count"], 1)

    def test_gold_regression_worsened_is_priority_a(self):
        report = build_review_queue(
            [],
            [{"stable_segment_key": "seg-1", "signals": ["gold_regression_worsened"]}],
        )
        self.assertEqual(report["items"][0]["priority"], "A")


class SourceIntegrityTests(unittest.TestCase):
    def test_hash_calculation(self):
        hashes = compute_source_hashes("raw", "normalized")
        self.assertEqual(len(hashes["raw_source_text_hash"]), 64)
        self.assertNotEqual(hashes["raw_source_text_hash"], hashes["normalized_source_text_hash"])

    def test_silent_normalization_detected_without_notes(self):
        flags = detect_silent_normalization("akicchāni", "akiccāni", [])
        self.assertEqual(flags, ["silent_source_normalization"])

    def test_silent_normalization_allowed_with_notes(self):
        flags = detect_silent_normalization("akicchāni", "akiccāni", ["spelling variant recorded"])
        self.assertEqual(flags, [])

    def test_round_trip_hash_mismatch_detected(self):
        record = {
            "stable_segment_key": "seg-1",
            "source_text_hash": "hash",
            "raw_source_text": "raw",
            "raw_source_text_hash": "bad",
        }
        result = check_integrity(record)
        self.assertIn("raw_source_hash_mismatch", result["flags"])


class ReferenceRegistryTests(unittest.TestCase):
    def test_reference_locator_only_passes(self):
        result = validate_reference_entry(
            {
                "stable_segment_key": "seg-1",
                "edition": "Example Edition",
                "ref_locator": "DN 1",
                "has_parallel": True,
                "divergence_flag": False,
            }
        )
        self.assertTrue(result["valid"])

    def test_external_translation_body_field_fails(self):
        result = validate_reference_entry(
            {
                "stable_segment_key": "seg-1",
                "edition": "Example Edition",
                "ref_locator": "DN 1",
                "translation_text": "protected body not allowed",
            }
        )
        self.assertFalse(result["valid"])

    def test_divergence_flag_is_registry_only(self):
        registry = {
            "entries": [
                {
                    "stable_segment_key": "seg-1",
                    "edition": "Example Edition",
                    "ref_locator": "DN 1",
                    "divergence_flag": True,
                    "divergence_category": "meaning",
                    "divergence_note": "Operator marked; no external text stored.",
                }
            ]
        }
        result = flag_reference_divergence("seg-1", registry)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["operator_marked"])
        self.assertNotIn("translation_text", result[0])


if __name__ == "__main__":
    unittest.main()
