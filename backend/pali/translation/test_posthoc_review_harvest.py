import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from backend.pali.scripts.run_step_3g_posthoc_review_harvest import run as run_cli
from backend.pali.translation.posthoc_review_harvest import run_posthoc_review_harvest


def review_queue_fixture():
    return {
        "schema_version": "pali_review_queue_reclassified_v1",
        "items": [
            {
                "stable_segment_key": "seg-app",
                "source_path": "romn/s0519m.mul.xml",
                "text_layer": "mula",
                "signals_before": ["grammar_uncertain"],
                "signals_after": ["grammar_uncertain"],
                "decision": "needs_human_review",
                "review_required_after_classification": True,
                "expert_question_candidate": False,
            },
            {
                "stable_segment_key": "seg-plain",
                "source_path": "romn/s0101m.mul.xml",
                "text_layer": "mula",
                "signals_before": ["contains_untranslated_pali"],
                "signals_after": ["pali_parenthetical_allowed"],
                "decision": "auto_accept_with_display_policy",
                "review_required_after_classification": False,
                "expert_question_candidate": False,
            },
        ],
    }


def findings_fixture():
    return {
        "schema_version": "pali_qa_findings_classifier_v1",
        "summary_after": {"human_needed_effective": 1},
        "items": review_queue_fixture()["items"],
    }


def parsed_fixture():
    return {
        "schema_version": "pali_pilot_300_batch_parsed_salvaged_v1",
        "items": [
            {
                "stable_segment_key": "seg-app",
                "source_path": "romn/s0519m.mul.xml",
                "text_layer": "mula",
                "original_text": "accantadiṭṭhaṃ",
                "literal_ko": "문자 그대로의 번역",
                "natural_ko": "자연스러운 번역",
            },
            {
                "stable_segment_key": "seg-holdout",
                "source_path": "romn/s0101m.mul.xml",
                "text_layer": "mula",
                "original_text": "dhamma",
                "literal_ko": "법",
                "natural_ko": "가르침",
            },
        ],
    }


def apparatus_crosscheck_fixture():
    return {
        "schema_version": "pali_apparatus_qa_crosscheck_v0",
        "items": [
            {
                "stable_segment_key": "seg-app",
                "classification": "apparatus_attests_variant",
                "apparatus_records": ["romn/s0519m.mul.xml:note:000001"],
                "auto_modify_source": False,
                "auto_modify_translation": False,
            }
        ],
    }


def variant_apparatus_fixture():
    return {
        "schema_version": "pali_variant_apparatus_v0",
        "records": [
            {
                "apparatus_id": "romn/s0519m.mul.xml:note:000001",
                "stable_segment_key": "seg-app",
                "source_path": "romn/s0519m.mul.xml",
                "main_reading": "accantadiṭṭhaṃ",
                "variant_text": "antaṃ niṭṭhaṃ",
                "raw_note_text": "antaṃ niṭṭhaṃ (sī.)",
                "sigla": ["sī"],
                "unknown_sigla": [],
                "evidence_strength_hint": "named_witness",
                "auto_apply": False,
            }
        ],
    }


def pilot_manifest_fixture(holdout_count=1):
    items = [
        {
            "stable_segment_key": "seg-app",
            "source_path": "romn/s0519m.mul.xml",
            "text_layer": "mula",
            "selection_group": "hard",
            "selection_bucket": "glossary_risk",
            "gold_candidate": False,
            "pool_candidate": None,
            "do_not_use_for_tuning_until_reviewed": False,
        }
    ]
    for index in range(holdout_count):
        items.append(
            {
                "stable_segment_key": "seg-holdout" if index == 0 else f"seg-holdout-{index}",
                "source_path": "romn/s0101m.mul.xml",
                "text_layer": "mula",
                "selection_group": "representative",
                "selection_bucket": "representative_stratified",
                "chunk_type": "prose",
                "length_bucket": "medium",
                "gold_candidate": True,
                "pool_candidate": "holdout_gold",
                "do_not_use_for_tuning_until_reviewed": True,
            }
        )
    return {"schema_version": "pali_pilot_300_manifest_v1", "items": items}


def run_fixture(root: Path, *, seed=None):
    input_paths = {
        "review_queue_reclassified": root / "review.json",
        "findings": root / "findings.json",
        "parsed": root / "parsed.json",
        "apparatus_crosscheck": root / "cross.json",
        "variant_apparatus": root / "apparatus.json",
        "pilot_300_manifest": root / "manifest.json",
        "gold_set": root / "gold.json",
        "seed_decisions": root / "seed.json",
    }
    for name, payload in [
        ("review_queue_reclassified", review_queue_fixture()),
        ("findings", findings_fixture()),
        ("parsed", parsed_fixture()),
        ("apparatus_crosscheck", apparatus_crosscheck_fixture()),
        ("variant_apparatus", variant_apparatus_fixture()),
        ("pilot_300_manifest", pilot_manifest_fixture()),
        ("gold_set", {"entries": []}),
    ]:
        input_paths[name].write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    if seed is not None:
        input_paths["seed_decisions"].write_text(json.dumps(seed, ensure_ascii=False), encoding="utf-8")
    out = root / "out"
    result = run_posthoc_review_harvest(
        review_queue_reclassified=review_queue_fixture(),
        findings=findings_fixture(),
        parsed_payload=parsed_fixture(),
        apparatus_crosscheck=apparatus_crosscheck_fixture(),
        variant_apparatus=variant_apparatus_fixture(),
        pilot_300_manifest=pilot_manifest_fixture(),
        gold_set={"entries": []},
        seed_decisions=seed,
        seed_decisions_path=input_paths["seed_decisions"],
        out_dir=out,
        input_paths=input_paths,
        pretty=True,
    )
    return out, result


class PosthocReviewHarvestTests(unittest.TestCase):
    def test_internal_notes_created_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, _ = run_fixture(Path(tmp))
            notes = json.loads((out / "internal_notes.json").read_text(encoding="utf-8"))
            item = notes["items"][0]
            self.assertEqual(item["apparatus_status"], "apparatus_attests_variant")
            self.assertEqual(item["variant_reading"], "antaṃ niṭṭhaṃ")
            self.assertFalse(item["auto_modify_translation"])
            self.assertFalse(item["auto_modify_source"])
            self.assertFalse(item["llm_retry_required"])

    def test_output_uses_attests_wording_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, _ = run_fixture(Path(tmp))
            combined = "\n".join(path.read_text(encoding="utf-8") for path in out.glob("*.json"))
            forbidden_a = "confirm" + "s"
            forbidden_b = "prove" + "s"
            self.assertNotIn(forbidden_a, combined)
            self.assertNotIn(forbidden_b, combined)
            self.assertIn("apparatus_attests_variant", combined)

    def test_missing_seed_file_creates_template_and_empty_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, result = run_fixture(Path(tmp))
            self.assertIn("seed_decisions_missing_manual_decisions_not_inferred", result["warnings"])
            self.assertTrue((out / "seed_decisions_template.json").exists())
            template = json.loads((out / "seed_decisions_template.json").read_text(encoding="utf-8"))
            self.assertEqual(template["items"][0]["seed_decision"], "unadjudicated")
            for name in [
                "glossary_candidates.json",
                "reference_table_candidates.json",
                "targeted_retry_candidates.json",
                "expert_review_candidates.json",
            ]:
                payload = json.loads((out / name).read_text(encoding="utf-8"))
                self.assertEqual(payload["items"], [])

    def test_seed_decision_file_is_ingested_exactly_and_candidates_follow_it(self):
        seed = {
            "schema_version": "seed_test",
            "decisions": [
                {
                    "stable_segment_key": "seg-app",
                    "seed_decision": "targeted_retry_candidate",
                    "decision_source": "manual_review_seed",
                    "llm_retry_required": True,
                    "expert_review_required": False,
                },
                {
                    "stable_segment_key": "seg-other",
                    "seed_decision": "glossary_candidate",
                    "decision_source": "manual_review_seed",
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            out, _ = run_fixture(Path(tmp), seed=seed)
            ingested = json.loads((out / "seed_decisions_ingested.json").read_text(encoding="utf-8"))
            self.assertEqual(ingested, seed)
            targeted = json.loads((out / "targeted_retry_candidates.json").read_text(encoding="utf-8"))
            glossary = json.loads((out / "glossary_candidates.json").read_text(encoding="utf-8"))
            self.assertEqual([item["stable_segment_key"] for item in targeted["items"]], ["seg-app"])
            self.assertEqual([item["stable_segment_key"] for item in glossary["items"]], ["seg-other"])

    def test_targeted_retry_not_inferred_automatically(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, _ = run_fixture(Path(tmp))
            targeted = json.loads((out / "targeted_retry_candidates.json").read_text(encoding="utf-8"))
            self.assertEqual(targeted["items"], [])

    def test_holdout_templates_are_not_frozen(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, _ = run_fixture(Path(tmp))
            template = json.loads((out / "holdout_adjudication_template.json").read_text(encoding="utf-8"))
            draft = json.loads((out / "holdout_gold_manifest_draft.json").read_text(encoding="utf-8"))
            self.assertFalse(template["holdout_gold_frozen"])
            self.assertFalse(template["items"][0]["frozen"])
            self.assertFalse(draft["frozen"])
            self.assertEqual(draft["future_batch_rule"]["total_future_batch_requests"], 1020)

    def test_run_manifest_records_local_only_invariants(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, _ = run_fixture(Path(tmp))
            manifest = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["step"], "3G-A")
            self.assertEqual(manifest["api_llm_calls"], 0)
            self.assertEqual(manifest["network_calls"], 0)
            self.assertFalse(manifest["translation_mutation"])
            self.assertFalse(manifest["source_mutation"])
            self.assertFalse(manifest["prompt_mutation"])
            self.assertFalse(manifest["glossary_mutation"])
            self.assertFalse(manifest["gold_set_mutation"])
            self.assertFalse(manifest["holdout_gold_frozen"])
            self.assertEqual(manifest["future_total_batch_requests"], 1020)

    def test_cli_writes_expected_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = {
                "review": root / "review.json",
                "findings": root / "findings.json",
                "parsed": root / "parsed.json",
                "cross": root / "cross.json",
                "apparatus": root / "apparatus.json",
                "manifest": root / "manifest.json",
                "gold": root / "gold.json",
                "seed": root / "missing_seed.json",
                "out": root / "out",
            }
            payloads = {
                "review": review_queue_fixture(),
                "findings": findings_fixture(),
                "parsed": parsed_fixture(),
                "cross": apparatus_crosscheck_fixture(),
                "apparatus": variant_apparatus_fixture(),
                "manifest": pilot_manifest_fixture(),
                "gold": {"entries": []},
            }
            for key, payload in payloads.items():
                paths[key].write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            result = run_cli(
                Namespace(
                    review_queue_reclassified=str(paths["review"]),
                    findings=str(paths["findings"]),
                    parsed=str(paths["parsed"]),
                    apparatus_crosscheck=str(paths["cross"]),
                    variant_apparatus=str(paths["apparatus"]),
                    pilot_300_manifest=str(paths["manifest"]),
                    gold_set=str(paths["gold"]),
                    seed_decisions=str(paths["seed"]),
                    out=str(paths["out"]),
                    pretty=True,
                )
            )
            self.assertEqual(result["status"], "STEP_3G_A_COMPLETE")
            for name in [
                "seed_decisions_ingested.json",
                "internal_notes.json",
                "glossary_candidates.json",
                "reference_table_candidates.json",
                "targeted_retry_candidates.json",
                "expert_review_candidates.json",
                "holdout_adjudication_template.json",
                "holdout_gold_manifest_draft.json",
                "step_3g_summary.md",
                "run_manifest.json",
            ]:
                self.assertTrue((paths["out"] / name).exists())


if __name__ == "__main__":
    unittest.main()
