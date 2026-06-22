import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.pali.importers.vri_xml import parse_vri_xml
from backend.pali.scripts.check_importer_note_preservation import run_check
from backend.pali.translation import variant_apparatus
from backend.pali.translation.prompts import render_korean_advanced_prompt_v1


SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<TEI.2>
  <text>
    <body xml:space="preserve">
      <p rend="nikaya">Khuddakanikāye</p>
      <div id="kn5" n="kn5" type="book">
        <head rend="book">Suttanipātapāḷi</head>
        <div id="kn5_1" n="kn5_1" type="vagga">
          <head rend="chapter">1. Uragavaggo</head>
          <p rend="bodytext" n="1">Evaṃ accantadiṭṭhaṃ <note>antaṃ niṭṭhaṃ (sī.)</note> ekaṃ samayaṃ.</p>
          <p rend="bodytext" n="2">Citation follows <note>ma. ni. 1.55</note> here.</p>
        </div>
      </div>
    </body>
  </text>
</TEI.2>
"""


def write_xml(root: Path, text: str = SAMPLE_XML) -> Path:
    path = root / "romn" / "test.mul.xml"
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")
    return path


class ImporterNotePreservationTests(unittest.TestCase):
    def test_importer_adds_variant_source_apparatus_metadata(self):
        with TemporaryDirectory() as tmp:
            xml_path = write_xml(Path(tmp))
            artifact = parse_vri_xml(xml_path, source_path="romn/test.mul.xml")
            segment = artifact["segments"][0]
            apparatus = segment["source_apparatus"]
            self.assertEqual(len(apparatus), 1)
            note = apparatus[0]
            self.assertEqual(note["note_type"], "variant")
            self.assertTrue(note["is_variant_apparatus"])
            self.assertEqual(note["variant_text"], "antaṃ niṭṭhaṃ")
            self.assertEqual(note["sigla"], ["sī"])
            self.assertEqual(note["evidence_strength_hint"], "named_witness")
            self.assertFalse(note["auto_apply"])

    def test_note_text_not_inserted_into_original_text(self):
        with TemporaryDirectory() as tmp:
            xml_path = write_xml(Path(tmp))
            segment = parse_vri_xml(xml_path, source_path="romn/test.mul.xml")["segments"][0]
            self.assertNotIn("antaṃ niṭṭhaṃ", segment["original_text"])
            self.assertNotIn("sī", segment["original_text"])
            self.assertIn("accantadiṭṭhaṃ", segment["original_text"])

    def test_original_text_key_hash_and_segment_count_remain_unchanged(self):
        with TemporaryDirectory() as tmp:
            xml_path = write_xml(Path(tmp))
            before = parse_vri_xml(xml_path, source_path="romn/test.mul.xml", preserve_source_apparatus=False)
            after = parse_vri_xml(xml_path, source_path="romn/test.mul.xml", preserve_source_apparatus=True)
            self.assertEqual(len(before["segments"]), len(after["segments"]))
            for old, new in zip(before["segments"], after["segments"]):
                self.assertEqual(old["original_text"], new["original_text"])
                self.assertEqual(old["stable_segment_key"], new["stable_segment_key"])
                self.assertEqual(old["source_text_hash"], new["source_text_hash"])
                self.assertEqual(old["xml_node_paths"], new["xml_node_paths"])
                old_without = dict(old)
                new_without = dict(new)
                old_without.pop("source_apparatus", None)
                new_without.pop("source_apparatus", None)
                self.assertEqual(old_without, new_without)

    def test_citation_note_not_variant_apparatus(self):
        with TemporaryDirectory() as tmp:
            xml_path = write_xml(Path(tmp))
            segment = parse_vri_xml(xml_path, source_path="romn/test.mul.xml")["segments"][1]
            note = segment["source_apparatus"][0]
            self.assertEqual(note["note_type"], "citation")
            self.assertFalse(note["is_variant_apparatus"])
            self.assertEqual(note["sigla"], [])
            self.assertEqual(note["citation_refs"], ["ma. ni. 1.55"])

    def test_step_3f_parser_helper_is_reused(self):
        with TemporaryDirectory() as tmp:
            xml_path = write_xml(Path(tmp))
            with patch(
                "backend.pali.translation.variant_apparatus.classify_note",
                wraps=variant_apparatus.classify_note,
            ) as mocked:
                parse_vri_xml(xml_path, source_path="romn/test.mul.xml")
            self.assertGreaterEqual(mocked.call_count, 2)

    def test_translation_prompt_input_remains_unchanged(self):
        with TemporaryDirectory() as tmp:
            xml_path = write_xml(Path(tmp))
            before = parse_vri_xml(xml_path, source_path="romn/test.mul.xml", preserve_source_apparatus=False)
            after = parse_vri_xml(xml_path, source_path="romn/test.mul.xml", preserve_source_apparatus=True)
            self.assertEqual(
                render_korean_advanced_prompt_v1(before["segments"][0]),
                render_korean_advanced_prompt_v1(after["segments"][0]),
            )
            self.assertNotIn("antaṃ niṭṭhaṃ", render_korean_advanced_prompt_v1(after["segments"][0]))

    def test_reimport_diff_check_reports_additive_only_change(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_xml(root)
            out = root / "report.json"
            report = run_check(
                source_root=root,
                source_paths=["romn/test.mul.xml"],
                out=out,
                pretty=True,
            )
            self.assertTrue(out.exists())
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["api_llm_calls"], 0)
            self.assertEqual(report["network_calls"], 0)
            self.assertFalse(report["translation_mutation"])
            self.assertFalse(report["source_mutation"])
            self.assertFalse(report["prompt_mutation"])
            self.assertFalse(report["glossary_mutation"])
            self.assertFalse(report["gold_set_mutation"])
            self.assertFalse(report["holdout_gold_frozen"])
            self.assertEqual(report["checked_files"], 1)
            self.assertEqual(report["checked_segments"], 2)
            self.assertEqual(report["original_text_mismatches"], 0)
            self.assertEqual(report["stable_segment_key_mismatches"], 0)
            self.assertEqual(report["source_text_hash_mismatches"], 0)
            self.assertEqual(report["segment_count_mismatches"], 0)
            self.assertEqual(report["non_additive_diffs"], 0)
            self.assertEqual(report["source_apparatus_records_added"], 2)


if __name__ == "__main__":
    unittest.main()
