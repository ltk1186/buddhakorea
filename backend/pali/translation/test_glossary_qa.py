import unittest
from pathlib import Path

from backend.pali.translation.glossary import load_glossary
from backend.pali.translation.glossary_qa import (
    build_glossary_qa_report,
    detect_avoid_ko_conflicts,
    detect_cross_term_collisions,
    map_citation_display,
    parse_composite_citation,
    reclassify_untranslated_pali_flags,
)


ROOT = Path(__file__).resolve().parents[3]
GLOSSARY_PATH = ROOT / "data" / "controlled_glossary.json"


class GlossaryQATest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.glossary = load_glossary(GLOSSARY_PATH)

    def test_declared_cross_avoid_pair_only_detects_collision(self):
        segment = self.segment(
            "dhīro paṇḍitoti pavuccati",
            [
                {"pali": "dhīra", "ko": "현자"},
                {"pali": "paṇḍita", "ko": "현자"},
                {"pali": "dhamma", "ko": "현자"},
            ],
        )
        signals = detect_cross_term_collisions(segment, self.glossary)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["signal"], "cross_term_collision_review")
        self.assertEqual({signals[0]["left_pali"], signals[0]["right_pali"]}, {"dhīra", "paṇḍita"})

    def test_all_pairs_comparison_is_not_used(self):
        segment = self.segment(
            "dhammaṃ khandhānaṃ",
            [
                {"pali": "dhamma", "ko": "법"},
                {"pali": "khandha", "ko": "법"},
            ],
        )
        self.assertEqual(detect_cross_term_collisions(segment, self.glossary), [])

    def test_batch_global_collision_is_diagnostic_not_hard_signal(self):
        report = build_glossary_qa_report(
            [
                self.segment("dhīro", [{"pali": "dhīra", "ko": "현자"}]),
                self.segment("paṇḍitoti", [{"pali": "paṇḍita", "ko": "현자"}]),
            ],
            self.glossary,
        )
        metrics = report["cross_term_metrics"]
        self.assertEqual(metrics["same_segment_collision_count"], 0)
        self.assertEqual(metrics["hard_signal_count"], 0)
        self.assertEqual(metrics["batch_global_collision_count"], 1)

    def test_uppala_absent_avoid_ko_is_not_violation(self):
        segment = self.segment("padumaṃ", [], literal_ko="연꽃", natural_ko="연꽃")
        self.assertEqual(detect_avoid_ko_conflicts(segment, self.glossary), [])

    def test_uppala_present_avoid_ko_is_violation_candidate(self):
        segment = self.segment("uppalaṃ", [], literal_ko="연꽃", natural_ko="연꽃")
        conflicts = detect_avoid_ko_conflicts(segment, self.glossary)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["pali"], "uppala")
        self.assertEqual(conflicts[0]["avoid_ko"], "연꽃")

    def test_paduma_present_lotus_is_not_uppala_violation(self):
        segment = self.segment("padumaṃ", [{"pali": "paduma", "ko": "연꽃"}], natural_ko="연꽃")
        conflicts = detect_avoid_ko_conflicts(segment, self.glossary)
        self.assertEqual(conflicts, [])

    def test_khandha_avoid_ko_requires_source_or_terms_trigger(self):
        no_khandha = self.segment(
            "saṅgaṇikārāmatā kammārāmatā",
            [{"pali": "kammārāmatā", "ko": "일을 즐김"}],
            literal_ko="무리와 어울림과 일을 즐김이다.",
            natural_ko="무리와 어울리고 일을 즐기는 것이다.",
        )
        self.assertEqual(detect_avoid_ko_conflicts(no_khandha, self.glossary), [])

        terms_trigger = self.segment(
            "pañca",
            [{"pali": "khandha", "ko": "무리"}],
            literal_ko="다섯 무리이다.",
            natural_ko="다섯 무리이다.",
        )
        conflicts = detect_avoid_ko_conflicts(terms_trigger, self.glossary)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["pali"], "khandha")
        self.assertEqual(conflicts[0]["avoid_ko"], "무리")
        self.assertTrue(conflicts[0]["hard_gate"])
        self.assertEqual(conflicts[0]["enforcement"], "hard")

    def test_khandha_muri_with_canonical_terms_is_advisory_not_hard(self):
        segment = self.segment(
            "pañcakkhandhā gaṇo",
            [{"pali": "khandha", "ko": "무더기"}],
            literal_ko="다섯 무더기와 무리이다.",
            natural_ko="다섯 무더기와 무리이다.",
        )
        conflicts = detect_avoid_ko_conflicts(segment, self.glossary)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["pali"], "khandha")
        self.assertEqual(conflicts[0]["avoid_ko"], "무리")
        self.assertFalse(conflicts[0]["hard_gate"])
        self.assertEqual(conflicts[0]["enforcement"], "advisory")

    def test_parenthetical_pali_is_reclassified_allowed(self):
        segment = self.segment(
            "yoniso manasikāra",
            [],
            natural_ko="마음에 잡도리함(yoniso manasikāra)을 말한다.",
            local_flags=["contains_untranslated_pali"],
        )
        result = reclassify_untranslated_pali_flags(segment)
        self.assertEqual(result["final_status"], "allowed")
        self.assertIn("allowed_parenthetical_pali", result["classification_counts"])

    def test_positive_control_true_untranslated_pali_is_preserved(self):
        segment = self.segment(
            "anicca dukkha anattā",
            [],
            natural_ko="이것은 anicca dukkha anattā이다.",
            local_flags=["contains_untranslated_pali"],
        )
        result = reclassify_untranslated_pali_flags(segment)
        self.assertEqual(result["final_status"], "possible_true_untranslated_pali")
        self.assertGreater(result["classification_counts"]["possible_true_untranslated_pali"], 0)

    def test_bracketed_pali_is_reclassified_allowed(self):
        segment = self.segment(
            "bhavaṅga",
            [],
            natural_ko="존재지속심[bhavaṅga]을 가리킨다.",
            local_flags=["contains_untranslated_pali"],
        )
        result = reclassify_untranslated_pali_flags(segment)
        self.assertEqual(result["final_status"], "allowed")
        self.assertIn("allowed_bracketed_pali", result["classification_counts"])

    def test_composite_citation_mapping_preserves_raw(self):
        mapped = parse_composite_citation("dī. ni. aṭṭha. 2.95")
        self.assertTrue(mapped["mapped"])
        self.assertEqual(mapped["raw"], "dī. ni. aṭṭha. 2.95")
        self.assertEqual(mapped["display"], "디가 니까야 주석 2.95")

    def test_tika_composite_citation_mapping(self):
        mapped = map_citation_display("sārattha. ṭī. 1.1")
        self.assertEqual(mapped["display"], "사라앗타 복주석 1.1")

    def test_build_report_has_citation_coverage(self):
        report = build_glossary_qa_report(
            [self.segment("dī. ni. aṭṭha. 2.95", [], natural_ko="(디가 니까야 주석 2.95)")],
            self.glossary,
        )
        self.assertEqual(report["summary"]["citation_candidate_count"], 1)
        self.assertEqual(report["summary"]["citation_mapped_count"], 1)
        self.assertEqual(report["summary"]["citation_mapping_coverage"], 1.0)

    @staticmethod
    def segment(source, terms, literal_ko="번역", natural_ko="번역", local_flags=None):
        return {
            "stable_segment_key": f"seg:{abs(hash(source))}",
            "original_text": source,
            "local_validator_flags": local_flags or [],
            "parsed_translation_json": {
                "literal_ko": literal_ko,
                "natural_ko": natural_ko,
                "terms": terms,
                "grammar_notes": [],
                "doctrinal_notes": [],
                "uncertainties": [],
                "quality_flags": [],
            },
        }


if __name__ == "__main__":
    unittest.main()
