import json
import tempfile
import unittest
from pathlib import Path

from backend.pali.translation.glossary import (
    calculate_term_consistency,
    detect_glossary_terms,
    extract_translation_head_terms,
    load_glossary,
    render_injection_block,
    select_glossary_entries_for_segment,
)


ROOT = Path(__file__).resolve().parents[3]
GLOSSARY_PATH = ROOT / "data" / "controlled_glossary.json"


class GlossaryInfrastructureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.glossary = load_glossary(GLOSSARY_PATH)

    def test_fixed_context_variant_and_needs_human_lookup(self):
        by_pali = self.glossary.by_pali
        self.assertEqual(by_pali["khandha"].type, "fixed")
        self.assertEqual(by_pali["saṅkhāra"].type, "context_variant")
        self.assertEqual(by_pali["abbokiṇṇa"].type, "needs_human")

    def test_exact_matching_handles_inflection_but_not_suffix_compounds(self):
        positive = detect_glossary_terms("khandhānaṃ dhammaṃ", self.glossary)
        self.assertIn("khandha", {entry.pali for entry in positive})
        self.assertIn("dhamma", {entry.pali for entry in positive})
        quoted = detect_glossary_terms("paṇḍitoti pavuccati", self.glossary)
        self.assertIn("paṇḍita", {entry.pali for entry in quoted})

        negative = detect_glossary_terms(
            "sīlasamādhipaññā viññāṇañcāyatanaṃ dhammacakkaṃ",
            self.glossary,
            match_mode="exact",
        )
        self.assertNotIn("dhamma", {entry.pali for entry in negative})

    def test_substring_mode_is_debug_only_and_shows_collision(self):
        exact = detect_glossary_terms("dhammacakkaṃ", self.glossary, match_mode="exact")
        substring = detect_glossary_terms("dhammacakkaṃ", self.glossary, match_mode="substring")
        self.assertNotIn("dhamma", {entry.pali for entry in exact})
        self.assertIn("dhamma", {entry.pali for entry in substring})

    def test_selection_caps_and_deduplicates(self):
        entries = select_glossary_entries_for_segment(
            "khandhānaṃ khandhānaṃ dhammaṃ saṅkhārā abbokiṇṇaṃ manasikāraṃ",
            self.glossary,
            max_n=3,
        )
        self.assertEqual(len(entries), 3)
        self.assertEqual(len({entry.pali for entry in entries}), 3)
        self.assertEqual(entries[0].type, "needs_human")

    def test_render_injection_block_marks_needs_human_as_non_authoritative(self):
        entries = select_glossary_entries_for_segment("abbokiṇṇaṃ khandhānaṃ", self.glossary)
        block = render_injection_block(entries)
        self.assertIn("Controlled glossary hints", block)
        self.assertIn("human review marker only", block)
        self.assertIn("Do not treat as authoritative", block)
        self.assertIn("khandha", block)

    def test_extract_translation_head_terms_requires_exact_pali_head(self):
        segment = {
            "parsed_translation_json": {
                "terms": [
                    {"pali": "khandha", "ko": "무더기"},
                    {"pali": "diṭṭha dhamma", "ko": "지금 여기"},
                    {"pali": "manasikāra", "ko": "마음에 잡도리함"},
                ]
            }
        }
        self.assertEqual(
            extract_translation_head_terms(segment, self.glossary),
            [("khandha", "무더기"), ("manasikāra", "마음에 잡도리함")],
        )

    def test_consistency_metric_detects_fixed_violation_and_avoid_ko(self):
        report = calculate_term_consistency(
            [
                self.segment("khandhānaṃ", "khandha", "무더기", natural_ko="무더기"),
                self.segment("khandhānaṃ", "khandha", "무리", natural_ko="무리"),
            ],
            self.glossary,
        )
        khandha = report["terms"]["khandha"]
        self.assertFalse(khandha["consistent"])
        self.assertIn("multiple_observed_ko", khandha["violations"])
        self.assertIn("avoid_ko_observed", khandha["violations"])

    def test_context_variant_multiple_allowed_renderings_are_not_violation(self):
        report = calculate_term_consistency(
            [
                self.segment("saṅkhārā", "saṅkhāra", "심리현상들"),
                self.segment("saṅkhārā", "saṅkhāra", "의도적 행위들"),
                self.segment("saṅkhārā", "saṅkhāra", "형성된 것들"),
            ],
            self.glossary,
        )
        sankhara = report["terms"]["saṅkhāra"]
        self.assertEqual(sankhara["unexpected_variants"], [])
        self.assertEqual(report["summary"]["context_unexpected_variants"], 0)

    def test_context_variant_unexpected_rendering_is_reported(self):
        report = calculate_term_consistency(
            [self.segment("saṅkhārā", "saṅkhāra", "구성물")],
            self.glossary,
        )
        self.assertEqual(report["terms"]["saṅkhāra"]["unexpected_variants"], ["구성물"])

    def test_needs_human_is_excluded_from_consistency_verdict(self):
        report = calculate_term_consistency(
            [self.segment("abbokiṇṇaṃ", "abbokiṇṇa", "순전함")],
            self.glossary,
        )
        abbokinna = report["terms"]["abbokiṇṇa"]
        self.assertTrue(abbokinna["consistency_excluded"])
        self.assertEqual(abbokinna["candidate_ko"], ["끊임없음", "순전함"])

    def test_avoid_ko_is_scoped_to_matched_source_or_exact_term(self):
        report = calculate_term_consistency(
            [
                {
                    "stable_segment_key": "seg:ordinary-muri",
                    "original_text": "naresu nārīsu",
                    "parsed_translation_json": {
                        "literal_ko": "남녀 무리 가운데",
                        "natural_ko": "남녀 무리 가운데",
                        "terms": [],
                    },
                },
                {
                    "stable_segment_key": "seg:dhira-pandita",
                    "original_text": "dhīro paṇḍito",
                    "parsed_translation_json": {
                        "literal_ko": "슬기로운 이는 현자이다.",
                        "natural_ko": "슬기로운 이는 현자이다.",
                        "terms": [{"pali": "dhīra", "ko": "슬기로운 이"}],
                    },
                },
            ],
            self.glossary,
        )
        self.assertEqual(report["terms"]["khandha"]["avoid_hits"], [])
        self.assertEqual(report["terms"]["dhīra"]["avoid_hits"], [])

    def test_load_glossary_from_file_has_no_global_state_requirement(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "glossary.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "test",
                        "entries": [
                            {
                                "pali": "testa",
                                "type": "fixed",
                                "status": "approved",
                                "canonical_ko": "테스트",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            loaded = load_glossary(path)
            self.assertEqual(loaded.schema_version, "test")
            self.assertIn("testa", loaded.by_pali)

    @staticmethod
    def segment(source_text, pali, ko, natural_ko=None):
        return {
            "stable_segment_key": f"seg:{pali}:{ko}",
            "original_text": source_text,
            "parsed_translation_json": {
                "literal_ko": ko,
                "natural_ko": natural_ko or ko,
                "terms": [{"pali": pali, "ko": ko}],
                "grammar_notes": [],
                "doctrinal_notes": [],
                "uncertainties": [],
                "quality_flags": [],
            },
        }


if __name__ == "__main__":
    unittest.main()
