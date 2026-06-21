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


def twelve_seed_records():
    decisions = [
        ("expert-1", "expert_review_candidate"),
        ("expert-2", "expert_review_candidate"),
        ("expert-3", "expert_review_candidate"),
        ("glossary-1", "glossary_candidate"),
        ("glossary-2", "glossary_candidate"),
        ("reference-1", "reference_table_candidate"),
        ("resolved-1", "low_severity"),
        ("resolved-2", "low_severity"),
        ("resolved-3", "no_action"),
        ("apparatus-1", "apparatus_internal_note"),
        ("apparatus-2", "apparatus_internal_note"),
        ("apparatus-3", "apparatus_internal_note"),
    ]
    return {
        "schema_version": "seed_test",
        "decisions": [
            {
                "stable_segment_key": key,
                "seed_decision": decision,
                "decision_source": "manual_review_seed",
                "rationale": f"rationale for {key}",
                "priority": "low",
                "target_hint": f"hint-{key}",
                "expert_review_required": decision == "expert_review_candidate",
                "llm_retry_required": decision == "targeted_retry_candidate",
            }
            for key, decision in decisions
        ],
    }


def review_queue_from_seed(seed_payload, *, stale_expert_flags=True):
    return {
        "schema_version": "pali_review_queue_reclassified_v1",
        "items": [
            {
                "stable_segment_key": record["stable_segment_key"],
                "source_path": "romn/test.mul.xml",
                "text_layer": "mula",
                "signals_before": ["grammar_uncertain"],
                "signals_after": ["grammar_uncertain"],
                "decision": "needs_human_review",
                "review_required_after_classification": True,
                "expert_question_candidate": stale_expert_flags,
            }
            for record in seed_payload["decisions"]
        ],
    }


def parsed_from_seed(seed_payload):
    return {
        "items": [
            {
                "stable_segment_key": record["stable_segment_key"],
                "source_path": "romn/test.mul.xml",
                "text_layer": "mula",
                "original_text": "test",
                "literal_ko": "직역",
                "natural_ko": "자연역",
            }
            for record in seed_payload["decisions"]
        ]
    }


def run_twelve_route_fixture(root: Path, *, seed=None, stale_expert_flags=True):
    seed = seed if seed is not None else twelve_seed_records()
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
    review_queue = review_queue_from_seed(seed, stale_expert_flags=stale_expert_flags)
    parsed = parsed_from_seed(seed)
    variant = {
        "records": [
            {
                "apparatus_id": f"id-{index}",
                "stable_segment_key": key,
                "source_path": "romn/test.mul.xml",
                "main_reading": "main",
                "variant_text": "variant",
                "raw_note_text": "variant (sī.)",
                "sigla": ["sī"],
            }
            for index, key in enumerate(["apparatus-1", "apparatus-2", "apparatus-3"], start=1)
        ]
    }
    manifest = {
        "items": [
            {
                "stable_segment_key": "holdout-1",
                "source_path": "romn/test.mul.xml",
                "gold_candidate": True,
                "pool_candidate": "holdout_gold",
                "do_not_use_for_tuning_until_reviewed": True,
            }
        ]
    }
    for name, payload in [
        ("review_queue_reclassified", review_queue),
        ("findings", {"items": review_queue["items"]}),
        ("parsed", parsed),
        ("apparatus_crosscheck", {"items": []}),
        ("variant_apparatus", variant),
        ("pilot_300_manifest", manifest),
        ("gold_set", {"entries": []}),
        ("seed_decisions", seed),
    ]:
        input_paths[name].write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    out = root / "out"
    run_posthoc_review_harvest(
        review_queue_reclassified=review_queue,
        findings={"items": review_queue["items"]},
        parsed_payload=parsed,
        apparatus_crosscheck={"items": []},
        variant_apparatus=variant,
        pilot_300_manifest=manifest,
        gold_set={"entries": []},
        seed_decisions=seed,
        seed_decisions_path=input_paths["seed_decisions"],
        out_dir=out,
        input_paths=input_paths,
        pretty=True,
    )
    return out


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
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            out, _ = run_fixture(Path(tmp), seed=seed)
            ingested = json.loads((out / "seed_decisions_ingested.json").read_text(encoding="utf-8"))
            self.assertEqual(ingested, seed)
            targeted = json.loads((out / "targeted_retry_candidates.json").read_text(encoding="utf-8"))
            self.assertEqual([item["stable_segment_key"] for item in targeted["items"]], ["seg-app"])

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
                "resolved_items.json",
                "remaining_routing_index.json",
                "holdout_adjudication_template.json",
                "holdout_gold_manifest_draft.json",
                "step_3g_summary.md",
                "run_manifest.json",
            ]:
                self.assertTrue((paths["out"] / name).exists())

    def test_seeded_expert_routing_overrides_stale_expert_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_twelve_route_fixture(Path(tmp), stale_expert_flags=True)
            experts = json.loads((out / "expert_review_candidates.json").read_text(encoding="utf-8"))
            keys = [item["stable_segment_key"] for item in experts["items"]]
            self.assertEqual(keys, ["expert-1", "expert-2", "expert-3"])
            self.assertTrue(all(item["seed_decision"] == "expert_review_candidate" for item in experts["items"]))
            self.assertTrue(all(item["expert_review_required"] is True for item in experts["items"]))
            for item in experts["items"]:
                self.assertIn("rationale", item)
                self.assertIn("priority", item)
                self.assertIn("target_hint", item)
                self.assertEqual(item["decision_source"], "manual_review_seed")

    def test_seeded_non_experts_do_not_leak_with_stale_expert_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_twelve_route_fixture(Path(tmp), stale_expert_flags=True)
            experts = json.loads((out / "expert_review_candidates.json").read_text(encoding="utf-8"))
            leaked = [item for item in experts["items"] if item.get("seed_decision") != "expert_review_candidate"]
            self.assertEqual(leaked, [])
            self.assertFalse(any(item.get("seed_decision") is None for item in experts["items"]))

    def test_review_required_alone_does_not_create_expert_candidate(self):
        seed = {"decisions": [{"stable_segment_key": "plain", "seed_decision": "low_severity"}]}
        with tempfile.TemporaryDirectory() as tmp:
            out = run_twelve_route_fixture(Path(tmp), seed=seed, stale_expert_flags=False)
            experts = json.loads((out / "expert_review_candidates.json").read_text(encoding="utf-8"))
            self.assertEqual(experts["items"], [])

    def test_resolved_items_contains_low_severity_and_no_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_twelve_route_fixture(Path(tmp))
            resolved = json.loads((out / "resolved_items.json").read_text(encoding="utf-8"))
            keys = [item["stable_segment_key"] for item in resolved["items"]]
            self.assertEqual(keys, ["resolved-1", "resolved-2", "resolved-3"])
            self.assertTrue(all(item["seed_decision"] in {"low_severity", "no_action"} for item in resolved["items"]))
            self.assertTrue(all(item["review_required"] is False for item in resolved["items"]))

    def test_remaining_routing_index_has_exactly_one_route_per_remaining_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_twelve_route_fixture(Path(tmp))
            routing = json.loads((out / "remaining_routing_index.json").read_text(encoding="utf-8"))
            self.assertEqual(len(routing["items"]), 12)
            summary = routing["summary"]
            self.assertEqual(summary["expert_review_candidate"], 3)
            self.assertEqual(summary["glossary_candidate"], 2)
            self.assertEqual(summary["reference_table_candidate"], 1)
            self.assertEqual(summary["targeted_retry_candidate"], 0)
            self.assertEqual(summary["resolved"], 3)
            self.assertEqual(summary["apparatus_internal_note"], 3)
            self.assertEqual(summary["duplicates"], 0)
            self.assertEqual(summary["missing"], 0)
            self.assertEqual(summary["seed_decision_null_leaks"], 0)

    def test_apparatus_internal_note_items_are_only_routing_index_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_twelve_route_fixture(Path(tmp))
            routing = json.loads((out / "remaining_routing_index.json").read_text(encoding="utf-8"))
            apparatus = [item for item in routing["items"] if item["route_bucket"] == "apparatus_internal_note"]
            self.assertEqual([item["stable_segment_key"] for item in apparatus], ["apparatus-1", "apparatus-2", "apparatus-3"])
            self.assertTrue(all(item["output_file"] == "internal_notes.json" for item in apparatus))
            experts = json.loads((out / "expert_review_candidates.json").read_text(encoding="utf-8"))
            expert_keys = {item["stable_segment_key"] for item in experts["items"]}
            self.assertFalse(expert_keys & {item["stable_segment_key"] for item in apparatus})

    def test_manifest_counts_match_output_lengths(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_twelve_route_fixture(Path(tmp))
            manifest = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
            counts = manifest["counts"]
            for key, filename in [
                ("expert_review_candidates", "expert_review_candidates.json"),
                ("glossary_candidates", "glossary_candidates.json"),
                ("reference_table_candidates", "reference_table_candidates.json"),
                ("targeted_retry_candidates", "targeted_retry_candidates.json"),
                ("resolved_items", "resolved_items.json"),
            ]:
                payload = json.loads((out / filename).read_text(encoding="utf-8"))
                self.assertEqual(counts[key], len(payload["items"]))
            routing = json.loads((out / "remaining_routing_index.json").read_text(encoding="utf-8"))
            self.assertEqual(counts["routing_duplicates"], routing["summary"]["duplicates"])
            self.assertEqual(counts["routing_missing"], routing["summary"]["missing"])
            self.assertEqual(counts["seed_decision_null_leaks"], routing["summary"]["seed_decision_null_leaks"])


if __name__ == "__main__":
    unittest.main()
