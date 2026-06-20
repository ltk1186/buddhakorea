import argparse
import json
import tempfile
import unittest
from pathlib import Path

from backend.pali.scripts.classify_pilot_300_qa_findings import run as run_cli
from backend.pali.translation.pali_qa_findings_classifier import (
    classify_review_findings,
    classify_review_item,
    detect_pali_runs,
)


def parsed_item(key="seg-001", literal="", natural="", terms=None, quality_flags=None, uncertainties=None):
    return {
        "stable_segment_key": key,
        "source_path": "romn/s0501a.att.xml",
        "text_layer": "atthakatha",
        "chunk_type": "prose",
        "length_bucket": "medium",
        "literal_ko": literal,
        "natural_ko": natural,
        "terms": terms or [],
        "grammar_notes": [],
        "doctrinal_notes": [],
        "uncertainties": uncertainties or [],
        "quality_flags": quality_flags or [],
        "local_validator_flags": ["contains_untranslated_pali"] if "ā" in literal + natural else [],
    }


def queue_item(key="seg-001", signals=None, priority="C"):
    return {
        "stable_segment_key": key,
        "source_path": "romn/s0501a.att.xml",
        "text_layer": "atthakatha",
        "chunk_type": "prose",
        "length_bucket": "medium",
        "priority": priority,
        "signals": signals or ["contains_untranslated_pali"],
        "dedup_group_key": f"{(signals or ['contains_untranslated_pali'])[0]}:{key}",
    }


def classify_one(item, signals=None):
    return classify_review_item(queue_item(item["stable_segment_key"], signals=signals), item)


class PaliQaFindingsClassifierTests(unittest.TestCase):
    def test_parenthetical_pali_after_korean_is_allowed(self):
        item = parsed_item(natural="역관(paṭiloma)은 반대 방향이라는 뜻이다.")
        result = classify_one(item)
        self.assertIn("pali_parenthetical_allowed", result["signals_after"])
        self.assertEqual(result["decision"], "auto_accept_with_display_policy")
        self.assertFalse(result["review_required_after_classification"])

    def test_korean_parenthetical_grammar_quote_allowed(self):
        item = parsed_item(natural="'큰 입구의 솥들의(mahāmukhaukkhalīnaṃ)'라는 것은 큰 솥들을 뜻한다.")
        result = classify_one(item)
        self.assertIn("pali_parenthetical_allowed", result["signals_after"])
        self.assertFalse(result["review_required_after_classification"])

    def test_pali_lemma_discussion_allowed(self):
        item = parsed_item(natural="'kho'라는 것은 강조의 뜻이다. avasāya가 끝, 마침을 말하는데 문맥은 분명하다.")
        result = classify_one(item)
        self.assertIn("pali_lemma_discussion_allowed", result["signals_after"])
        self.assertFalse(result["review_required_after_classification"])

    def test_bare_uncovered_pali_is_strict(self):
        item = parsed_item(natural="이 문장은 anattā를 그대로 남긴다.")
        result = classify_one(item)
        self.assertIn("possible_untranslated_pali_strict", result["signals_after"])
        self.assertTrue(result["review_required_after_classification"])
        self.assertEqual(result["decision"], "needs_human_review")
        self.assertEqual(result["uncovered_pali_runs"][0]["run_text"], "anattā")

    def test_terms_explained_pali_is_not_strict(self):
        item = parsed_item(
            natural="이 문맥에서 gatinimitta는 갈 곳의 표상을 뜻한다.",
            terms=[{"pali": "gatinimitta", "ko": "갈 곳의 표상", "gloss": "sign", "note": ""}],
        )
        result = classify_one(item)
        self.assertIn("terms_explained_pali_allowed", result["signals_after"])
        self.assertFalse(result["review_required_after_classification"])

    def test_proper_name_candidate_is_allowlist_candidate(self):
        item = parsed_item(natural="Visuddhimagga는 청정도론으로 알려져 있다.")
        result = classify_one(item)
        self.assertEqual(result["decision"], "glossary_or_allowlist_candidate")
        self.assertFalse(result["review_required_after_classification"])

    def test_mixed_allowed_and_uncovered_runs_uses_worst_case(self):
        item = parsed_item(natural="역관(paṭiloma)은 설명되었지만 anattā는 그대로 남았다.")
        result = classify_one(item)
        self.assertIn("pali_parenthetical_allowed", result["signals_after"])
        self.assertIn("possible_untranslated_pali_strict", result["signals_after"])
        self.assertTrue(result["review_required_after_classification"])
        self.assertFalse(result["run_worst_case_passed"])

    def test_allowed_untranslated_with_grammar_uncertain_stays_human_needed(self):
        item = parsed_item(
            natural="역관(paṭiloma)은 반대 방향이라는 뜻이다.",
            quality_flags=["grammar_uncertain"],
            uncertainties=["복합어 해석 가능성이 있다."],
        )
        result = classify_one(item, signals=["contains_untranslated_pali", "grammar_uncertain"])
        self.assertIn("pali_parenthetical_allowed", result["signals_after"])
        self.assertIn("grammar_uncertain_retained", result["signals_after"])
        self.assertTrue(result["review_required_after_classification"])
        self.assertEqual(result["decision"], "needs_human_review")
        self.assertEqual(result["grammar_uncertain_hint"], "possible_high")
        self.assertTrue(result["expert_question_candidate"])

    def test_grammar_uncertain_never_auto_accepts_even_without_pali(self):
        item = parsed_item(natural="불확실성이 있는 자연역", quality_flags=["grammar_uncertain"], uncertainties=["부정 범위가 애매하다."])
        result = classify_one(item, signals=["grammar_uncertain"])
        self.assertTrue(result["review_required_after_classification"])
        self.assertEqual(result["decision"], "needs_human_review")
        self.assertNotIn(result["decision"], {"auto_accept", "auto_accept_with_display_policy"})

    def test_run_detection_records_coverage_fields(self):
        item = parsed_item(natural="그것들로(tehi)라고 설명하고 anattā는 남았다.")
        runs = detect_pali_runs(item)
        self.assertTrue(any(run["run_text"] == "tehi" for run in runs))
        self.assertTrue(any(run["run_text"] == "anattā" for run in runs))

    def test_findings_summary_and_seed_are_deterministic(self):
        parsed = {"items": [parsed_item("seg-001", natural="역관(paṭiloma)은 설명이다.")]}
        review_queue = {"summary": {"human_needed_count": 1, "priority_counts": {"C": 1}}, "items": [queue_item("seg-001")]}
        first = classify_review_findings(review_queue=review_queue, parsed_payload=parsed)
        second = classify_review_findings(review_queue=review_queue, parsed_payload=parsed)
        self.assertEqual(first["summary_after"]["human_needed_effective"], 0)
        self.assertEqual(first["sampling_recommendation"], second["sampling_recommendation"])
        self.assertEqual(first["run_coverage_summary"]["uncovered_pali_runs"], 0)

    def test_cli_writes_outputs_without_overwriting_inputs_and_300_fixture_reduces_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parsed_items = []
            queue_items = []
            for index in range(67):
                key = f"auto-{index:03d}"
                parsed_items.append(parsed_item(key, natural=f"역관(paṭiloma)은 설명 {index}이다."))
                queue_items.append(queue_item(key))
            for index in range(6):
                key = f"grammar-{index:03d}"
                parsed_items.append(parsed_item(key, natural=f"문장 {index}", quality_flags=["grammar_uncertain"], uncertainties=["복합어 해석 가능성이 있다."]))
                queue_items.append(queue_item(key, signals=["grammar_uncertain"], priority="B"))
            for index in range(5):
                key = f"both-{index:03d}"
                parsed_items.append(parsed_item(key, natural=f"역관(paṭiloma)은 설명 {index}이다.", quality_flags=["grammar_uncertain"], uncertainties=["부정 범위가 애매하다."]))
                queue_items.append(queue_item(key, signals=["contains_untranslated_pali", "grammar_uncertain"], priority="B"))
            key = "needs-human"
            parsed_items.append(parsed_item(key, natural="보살(paṭiloma)은 설명이다.", quality_flags=["needs_human_review"]))
            queue_items.append(queue_item(key, signals=["contains_untranslated_pali", "needs_human_review"], priority="B"))

            review_queue = {
                "schema_version": "pali_review_queue_v1_2",
                "summary": {"human_needed_count": 79, "priority_counts": {"B": 12, "C": 67}},
                "items": queue_items,
            }
            paths = {
                "review_queue": root / "review_queue.json",
                "review_report": root / "review_report.md",
                "parsed": root / "parsed.json",
                "out": root / "classified",
            }
            paths["review_queue"].write_text(json.dumps(review_queue, ensure_ascii=False), encoding="utf-8")
            paths["review_report"].write_text("# report\nflag false positive placeholder", encoding="utf-8")
            paths["parsed"].write_text(json.dumps({"items": parsed_items}, ensure_ascii=False), encoding="utf-8")
            original_queue = paths["review_queue"].read_text(encoding="utf-8")
            result = run_cli(
                argparse.Namespace(
                    review_queue=str(paths["review_queue"]),
                    review_report=str(paths["review_report"]),
                    parsed=str(paths["parsed"]),
                    out=str(paths["out"]),
                    pretty=True,
                )
            )
            self.assertEqual(result["status"], "CLASSIFICATION_COMPLETE")
            self.assertEqual(result["input_human_needed"], 79)
            self.assertEqual(result["effective_human_needed"], 12)
            self.assertEqual(result["auto_allowed"], 67)
            self.assertEqual(result["possible_untranslated_pali_strict"], 0)
            self.assertEqual(result["grammar_uncertain_auto_accepted"], 0)
            self.assertTrue((paths["out"] / "findings.json").exists())
            self.assertTrue((paths["out"] / "findings.md").exists())
            self.assertTrue((paths["out"] / "review_queue_reclassified.json").exists())
            self.assertTrue((paths["out"] / "pali_qa_pattern_decisions_v1.json").exists())
            self.assertEqual(paths["review_queue"].read_text(encoding="utf-8"), original_queue)
            md = (paths["out"] / "findings.md").read_text(encoding="utf-8")
            self.assertIn("flag-level false positives, not certified-correct translations", md)


if __name__ == "__main__":
    unittest.main()
