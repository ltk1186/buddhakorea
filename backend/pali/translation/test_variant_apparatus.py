import argparse
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from backend.pali.importers.vri_xml import parse_vri_xml
from backend.pali.scripts.extract_variant_apparatus import run as run_cli
from backend.pali.translation.variant_apparatus import (
    classify_note,
    extract_source_apparatus,
    parse_sigla,
    run_variant_apparatus_extraction,
)


SYNTHETIC_XML = """<?xml version="1.0" encoding="UTF-16"?>
<TEI.2>
  <text>
    <body>
      <p rend="bodytext">accantadiṭṭhaṃ <note>antaṃ niṭṭhaṃ (sī.)</note> nibbānaṃ ārādheti.</p>
      <p rend="bodytext">citation carrier <note>ma. ni. 1.55</note> iti.</p>
      <p rend="bodytext">nettī <note>nettī (ka.)</note> padaṃ.</p>
    </body>
  </text>
</TEI.2>
"""


def write_xml(root: Path, rel="romn/test.mul.xml", text=SYNTHETIC_XML) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-16")
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic_payloads(root: Path):
    xml_path = write_xml(root)
    artifact = parse_vri_xml(xml_path, source_path="romn/test.mul.xml")
    segments = artifact["segments"]
    parsed_items = []
    for segment in segments:
        parsed_items.append(
            {
                "stable_segment_key": segment["stable_segment_key"],
                "source_path": segment["source_path"],
                "original_text": segment["original_text"],
                "literal_ko": "직역",
                "natural_ko": "자연역",
                "schema_valid": True,
                "status": "succeeded",
                "local_validator_flags": [],
                "quality_flags": [],
            }
        )
    first_key = segments[0]["stable_segment_key"]
    second_key = segments[1]["stable_segment_key"]
    third_key = segments[2]["stable_segment_key"]
    parsed = {"items": parsed_items}
    review_queue = {
        "items": [
            {
                "stable_segment_key": first_key,
                "source_path": "romn/test.mul.xml",
                "review_required_after_classification": True,
                "signals_before": ["grammar_uncertain"],
                "signals_after": ["grammar_uncertain"],
            }
        ]
    }
    findings = {"items": []}
    return xml_path, parsed, review_queue, findings, first_key, second_key, third_key


class VariantApparatusUnitTests(unittest.TestCase):
    def test_parse_sigla_extracts_single_and_multiple(self):
        self.assertEqual(parse_sigla("antaṃ niṭṭhaṃ (sī.)")["sigla"], ["sī"])
        self.assertEqual(parse_sigla("nettī (ka.)")["sigla"], ["ka"])
        self.assertEqual(parse_sigla("mahākaccānena (sī. syā. pī.)")["sigla"], ["sī", "syā", "pī"])

    def test_unknown_sigla_are_preserved_and_variant_text_excludes_sigla(self):
        result = parse_sigla("reading (zz.)")
        self.assertEqual(result["unknown_sigla"], ["zz"])
        self.assertEqual(result["variant_text"], "reading")

    def test_note_type_classification_distinguishes_citation_before_siglum(self):
        citation = classify_note("ma. ni. 1.55")
        self.assertEqual(citation.note_type, "citation")
        self.assertFalse(citation.is_variant_apparatus)
        self.assertEqual(citation.sigla, [])
        self.assertEqual(citation.citation_refs, ["ma. ni. 1.55"])
        variant = classify_note("nettī (ka.)")
        self.assertEqual(variant.note_type, "variant")
        self.assertTrue(variant.is_variant_apparatus)
        self.assertEqual(variant.sigla, ["ka"])
        self.assertEqual(variant.evidence_strength_hint, "weak_or_unspecified")

    def test_xml_note_records_are_extracted_from_utf16_without_auto_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xml_path = write_xml(root)
            before = sha(xml_path)
            extraction = extract_source_apparatus(root, "romn/test.mul.xml")
            after = sha(xml_path)
            self.assertEqual(before, after)
            self.assertEqual(extraction["note_count"], 3)
            records = extraction["note_records"]
            first = records[0]
            self.assertEqual(first["note_type"], "variant")
            self.assertTrue(first["is_variant_apparatus"])
            self.assertEqual(first["anchor_text"], "accantadiṭṭhaṃ")
            self.assertTrue(first["anchor_uncertain"])
            self.assertFalse(first["auto_apply"])
            self.assertEqual(records[1]["note_type"], "citation")
            self.assertFalse(records[1]["is_variant_apparatus"])


class VariantApparatusPipelineTests(unittest.TestCase):
    def test_synthetic_accantadittham_case_becomes_apparatus_attests_variant(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, parsed, review_queue, findings, first_key, _, _ = synthetic_payloads(root)
            result = run_variant_apparatus_extraction(
                review_queue_reclassified=review_queue,
                findings=findings,
                parsed_payload=parsed,
                source_root=root,
                targets_payload={
                    "targets": [
                        {
                            "stable_segment_key": first_key,
                            "source_path": "romn/test.mul.xml",
                            "target_hint": "accantadiṭṭhaṃ",
                        }
                    ]
                },
            )
            item = result["crosscheck"]["items"][0]
            self.assertEqual(item["classification"], "apparatus_attests_variant")
            self.assertFalse(item["auto_modify_translation"])
            self.assertFalse(item["auto_modify_source"])
            forbidden = "apparatus_" + "confirms_variant"
            self.assertNotIn(forbidden, json.dumps(result, ensure_ascii=False))

    def test_missing_source_and_no_nearby_note_classifications(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, parsed, review_queue, findings, _, second_key, _ = synthetic_payloads(root)
            missing = run_variant_apparatus_extraction(
                review_queue_reclassified=review_queue,
                findings=findings,
                parsed_payload=parsed,
                source_root=root,
                targets_payload={
                    "targets": [
                        {
                            "stable_segment_key": "missing-key",
                            "source_path": "romn/missing.mul.xml",
                            "target_hint": "missing",
                        }
                    ]
                },
            )
            self.assertEqual(missing["crosscheck"]["items"][0]["classification"], "apparatus_extraction_missing_source")
            citation_only = run_variant_apparatus_extraction(
                review_queue_reclassified=review_queue,
                findings=findings,
                parsed_payload=parsed,
                source_root=root,
                targets_payload={
                    "targets": [
                        {
                            "stable_segment_key": second_key,
                            "source_path": "romn/test.mul.xml",
                            "target_hint": "carrier",
                        }
                    ]
                },
            )
            self.assertEqual(citation_only["crosscheck"]["items"][0]["classification"], "no_apparatus_variant")

    def test_nearby_variant_without_target_hint_is_not_attestation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, parsed, review_queue, findings, first_key, _, _ = synthetic_payloads(root)
            result = run_variant_apparatus_extraction(
                review_queue_reclassified=review_queue,
                findings=findings,
                parsed_payload=parsed,
                source_root=root,
                targets_payload={
                    "targets": [
                        {
                            "stable_segment_key": first_key,
                            "source_path": "romn/test.mul.xml",
                            "target_hint": "notpresent",
                        }
                    ]
                },
            )
            self.assertEqual(result["crosscheck"]["items"][0]["classification"], "apparatus_has_variant_nearby")
            record = result["variant_apparatus"]["records"][0]
            self.assertEqual(record["attribution_confidence"], "high")

    def test_full_300_loss_summary_fields_exist_and_citation_notes_are_excluded_from_variant_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, parsed, review_queue, findings, first_key, _, _ = synthetic_payloads(root)
            result = run_variant_apparatus_extraction(
                review_queue_reclassified=review_queue,
                findings=findings,
                parsed_payload=parsed,
                source_root=root,
                targets_payload={
                    "targets": [
                        {
                            "stable_segment_key": first_key,
                            "source_path": "romn/test.mul.xml",
                            "target_hint": "accantadiṭṭhaṃ",
                        }
                    ]
                },
            )
            summary = result["premise_check"]["pilot_300_apparatus_loss_summary"]
            self.assertIn("segments_with_variant_apparatus_in_source", summary)
            self.assertIn("segments_with_variant_apparatus_missing_from_translation_input", summary)
            self.assertEqual(summary["citation_note_records_in_300_source_scope"], 1)
            self.assertTrue(all(record["note_type"] == "variant" for record in result["variant_apparatus"]["records"]))

    def test_cli_writes_outputs_without_mutating_inputs_or_using_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xml_path, parsed, review_queue, findings, first_key, _, _ = synthetic_payloads(root)
            input_dir = root / "inputs"
            input_dir.mkdir()
            paths = {
                "review_queue": input_dir / "review_queue_reclassified.json",
                "findings": input_dir / "findings.json",
                "parsed": input_dir / "parsed.json",
                "targets": input_dir / "targets.json",
                "out": root / "out",
            }
            paths["review_queue"].write_text(json.dumps(review_queue, ensure_ascii=False), encoding="utf-8")
            paths["findings"].write_text(json.dumps(findings, ensure_ascii=False), encoding="utf-8")
            paths["parsed"].write_text(json.dumps(parsed, ensure_ascii=False), encoding="utf-8")
            paths["targets"].write_text(
                json.dumps(
                    {
                        "schema_version": "pali_variant_apparatus_targets_v0",
                        "targets": [
                            {
                                "stable_segment_key": first_key,
                                "source_path": "romn/test.mul.xml",
                                "target_hint": "accantadiṭṭhaṃ",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            parsed_before = sha(paths["parsed"])
            source_before = sha(xml_path)
            result = run_cli(
                argparse.Namespace(
                    review_queue_reclassified=str(paths["review_queue"]),
                    findings=str(paths["findings"]),
                    parsed=str(paths["parsed"]),
                    source_root=str(root),
                    targets=str(paths["targets"]),
                    out=str(paths["out"]),
                    max_targets=20,
                    window_chars=160,
                    pretty=True,
                )
            )
            self.assertEqual(result["status"], "VARIANT_APPARATUS_EXTRACTION_COMPLETE")
            self.assertEqual(result["api_llm_calls"], 0)
            self.assertEqual(result["network_calls"], 0)
            self.assertFalse(result["cross_script_collation"])
            self.assertEqual(parsed_before, sha(paths["parsed"]))
            self.assertEqual(source_before, sha(xml_path))
            for name in [
                "apparatus_premise_check.json",
                "variant_apparatus.json",
                "apparatus_qa_crosscheck.json",
                "apparatus_findings.md",
                "run_manifest.json",
            ]:
                self.assertTrue((paths["out"] / name).exists())
            report = (paths["out"] / "apparatus_findings.md").read_text(encoding="utf-8")
            source_typo_claim = "confirmed" + " as a source typo"
            forbidden = "apparatus_" + "confirms_variant"
            self.assertNotIn(source_typo_claim, report)
            self.assertNotIn(forbidden, report)
            manifest = json.loads((paths["out"] / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["api_llm_calls"], 0)
            self.assertEqual(manifest["network_calls"], 0)
            self.assertFalse(manifest["source_mutation"])
            self.assertFalse(manifest["translation_mutation"])


if __name__ == "__main__":
    unittest.main()
