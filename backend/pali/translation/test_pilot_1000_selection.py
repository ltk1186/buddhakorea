from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from backend.pali.importers.vri_xml import parse_vri_xml
from backend.pali.translation import pilot_1000_selection as sel


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def make_item(
    index: int,
    *,
    layer: str = "mula",
    length: str = "short",
    chunk: str = "prose",
    text: str = "ordinary source text",
    source_path: str | None = None,
    pitaka: str = "sutta",
) -> dict:
    key = f"vri:romn:test:{index:06d}"
    source_path = source_path or f"romn/test{index % 17:02d}m.mul.xml"
    return {
        "stable_segment_key": key,
        "source_path": source_path,
        "source_file": Path(source_path).name,
        "source_text_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "source_commit": sel.PINNED_INVENTORY_COMMIT,
        "text_layer": layer,
        "length_bucket": length,
        "chunk_type": chunk,
        "pitaka": pitaka,
        "nikaya": "Synthetic",
        "canonical_ref": f"ref-{index}",
        "heading_path": [],
        "sort_order": index,
        "char_count": len(text),
        "original_text": text,
        "normalized_text": text,
    }


def synthetic_inventory() -> tuple[list[dict], set[str]]:
    items: list[dict] = []
    apparatus_keys: set[str] = set()
    index = 0

    for _ in range(60):
        index += 1
        item = make_item(index, layer="mula", length="short", chunk="prose", text=f"apparatus neutral {index}")
        apparatus_keys.add(item["stable_segment_key"])
        items.append(item)
    for _ in range(120):
        index += 1
        items.append(make_item(index, layer="tika", length="long", chunk="prose", text=f"tika long {index}", source_path=f"romn/t{index:04d}.tik.xml"))
    for _ in range(100):
        index += 1
        items.append(make_item(index, layer="atthakatha", length="long", chunk="prose", text=f"atthakatha long {index}", source_path=f"romn/a{index:04d}.att.xml"))
    for _ in range(80):
        index += 1
        items.append(make_item(index, layer="mula", length="medium", chunk="prose", text=f"katamo dhammo {index}", source_path=f"romn/abh{index:04d}m.mul.xml", pitaka="abhidhamma"))
    for _ in range(70):
        index += 1
        items.append(make_item(index, layer="mula", length="medium", chunk="verse", text=f"verse gatha {index}"))
    for _ in range(80):
        index += 1
        items.append(make_item(index, layer="mula", length="medium", chunk="prose", text=f"dī. ni. citation {index}"))

    for layer in ("mula", "atthakatha", "tika"):
        for length in ("short", "medium", "long"):
            for chunk in ("prose", "verse"):
                for _ in range(95):
                    index += 1
                    path_suffix = "mul" if layer == "mula" else "att" if layer == "atthakatha" else "tik"
                    items.append(
                        make_item(
                            index,
                            layer=layer,
                            length=length,
                            chunk=chunk,
                            text=f"representative ordinary {layer} {length} {chunk} {index}",
                            source_path=f"romn/r{index:05d}.{path_suffix}.xml",
                        )
                    )
    return items, apparatus_keys


def write_fixture_inputs(root: Path, inventory: list[dict], silver_keys: list[str] | None = None) -> dict[str, Path]:
    paths = {
        "inventory": root / "inventory.json",
        "pilot300": root / "pilot300.json",
        "pilot75": root / "pilot75.json",
        "step4": root / "step4.json",
        "silver": root / "silver.json",
        "gold": root / "gold.json",
        "step4_decision": root / "final_decision.json",
        "step4_handoff": root / "handoff.md",
        "importer_check": root / "importer_check.json",
        "out": root / "out",
    }
    write_json(paths["inventory"], {"schema_version": "pali_segment_inventory_cache_v1", "source_commit": sel.PINNED_INVENTORY_COMMIT, "items": inventory})
    write_json(paths["pilot300"], {"items": [{"stable_segment_key": inventory[0]["stable_segment_key"]}]})
    write_json(paths["pilot75"], {"items": [{"stable_segment_key": inventory[1]["stable_segment_key"]}]})
    write_json(paths["step4"], {"items": [{"stable_segment_key": inventory[2]["stable_segment_key"]}]})
    silver_items = [{"stable_segment_key": key, "active_canary": True, "not_gold_standard": True, "frozen": False} for key in (silver_keys or [inventory[3]["stable_segment_key"]])]
    write_json(paths["silver"], {"items": silver_items})
    write_json(paths["gold"], {"entries": [{"stable_segment_key": inventory[4]["stable_segment_key"]}]})
    write_json(paths["step4_decision"], {"operator_decision": "adopt_response_schema_for_1000_pilot_with_salvage_fallback"})
    paths["step4_handoff"].write_text("silver canary advisory only", encoding="utf-8")
    write_json(paths["importer_check"], {"status": "PASS"})
    return paths


def run_fixture_selection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    inventory, apparatus_keys = synthetic_inventory()
    paths = write_fixture_inputs(tmp_path, inventory)

    def fake_apparatus_counts(_inventory, *, source_root, source_commit=sel.PINNED_INVENTORY_COMMIT):
        return {key: 1 for key in apparatus_keys}, {
            "method": "fake_step_3h_importer_reparse_for_unit_test",
            "source_files_checked": 1,
            "apparatus_bearing_segment_count": len(apparatus_keys),
            "variant_apparatus_records": len(apparatus_keys),
            "missing_files": [],
            "parse_errors": [],
        }

    monkeypatch.setattr(sel, "compute_source_apparatus_counts", fake_apparatus_counts)
    result = sel.run_selection(
        inventory_path=paths["inventory"],
        out_dir=paths["out"],
        source_root=tmp_path,
        pilot_300_manifest=paths["pilot300"],
        pilot_75_paths=[paths["pilot75"]],
        step4_selection=paths["step4"],
        silver_draft=paths["silver"],
        gold_set=paths["gold"],
        step4_final_decision=paths["step4_decision"],
        step4_handoff=paths["step4_handoff"],
        importer_check=paths["importer_check"],
        pretty=True,
    )
    manifest = json.loads((paths["out"] / "pilot_1000_v1_manifest.json").read_text(encoding="utf-8"))
    validation = json.loads((paths["out"] / "pilot_1000_v1_validation.json").read_text(encoding="utf-8"))
    run_manifest = json.loads((paths["out"] / "pilot_1000_v1_run_manifest.json").read_text(encoding="utf-8"))
    return result, manifest, validation, run_manifest, paths


def test_deterministic_selection_counts_and_disjointness(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    result, manifest, validation, run_manifest, _paths = run_fixture_selection(monkeypatch, tmp_path)
    assert result["selected_count"] == 1000
    assert validation["selected_count"] == 1000
    assert validation["representative_count"] == 700
    assert validation["hard_count"] == 300
    assert validation["duplicate_count"] == 0
    assert validation["overlap_with_75_count"] == 0
    assert validation["overlap_with_300_count"] == 0
    assert validation["overlap_with_step4_count"] == 0
    assert validation["silver_canary_in_main_manifest_count"] == 0
    assert validation["gold_holdout_count"] == 0
    assert manifest["response_schema_default_for_1000"] is True
    assert manifest["salvage_cascade_fallback"] is True
    assert run_manifest["api_llm_calls"] == 0
    assert run_manifest["network_calls"] == 0
    assert run_manifest["step6_cost_estimate_started"] is False
    assert run_manifest["inventory_source_commit"] == sel.PINNED_INVENTORY_COMMIT


def test_same_inputs_same_selection_hash(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    first = run_fixture_selection(monkeypatch, tmp_path / "a")[2]["selection_content_sha256"]
    second = run_fixture_selection(monkeypatch, tmp_path / "b")[2]["selection_content_sha256"]
    assert first == second


def test_representative_mix_and_hard_bucket_priority(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _result, manifest, validation, _run_manifest, _paths = run_fixture_selection(monkeypatch, tmp_path)
    reps = [item for item in manifest["items"] if item["selection_group"] == "representative"]
    rep_layers = Counter(item["text_layer"] for item in reps)
    assert abs(rep_layers["mula"] - 365) <= 15
    assert abs(rep_layers["atthakatha"] - 265) <= 15
    assert abs(rep_layers["tika"] - 70) <= 15
    assert validation["by_selection_bucket"]["apparatus_bearing"] == 40
    overlap_item = {
        "text_layer": "tika",
        "length_bucket": "long",
        "chunk_type": "verse",
        "source_apparatus_count": 1,
        "has_source_apparatus": True,
        "pitaka": "abhidhamma",
        "source_path": "romn/abh01t.tik.xml",
        "normalized_text": "katamo dī. ni.",
    }
    assert sel.primary_hard_bucket(overlap_item) == "apparatus_bearing"


def test_validation_fails_on_duplicates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _result, manifest, _validation, _run_manifest, _paths = run_fixture_selection(monkeypatch, tmp_path)
    manifest["items"][1]["stable_segment_key"] = manifest["items"][0]["stable_segment_key"]
    validation = sel.validate_manifest(manifest, prior_keys={"pilot75": set(), "pilot300": set(), "step4": set(), "gold": set()}, step4_keys=set(), silver_keys=set())
    assert validation["validation_status"] == "FAIL"
    assert validation["duplicate_count"] == 1


def test_soft_guardrail_warning() -> None:
    items = [
        {
            "stable_segment_key": f"k{i}",
            "source_path": "romn/test.mul.xml",
            "source_text_hash": f"h{i}",
            "selection_group": "representative" if i < 700 else "hard",
            "text_layer": "mula",
            "length_bucket": "short",
            "chunk_type": "prose",
            "gold_holdout": False,
            "silver_canary": False,
        }
        for i in range(1000)
    ]
    manifest = {"items": items, "warnings": [], "selection_content_sha256": "sha"}
    validation = sel.validate_manifest(manifest, prior_keys={"pilot75": set(), "pilot300": set(), "step4": set(), "gold": set()}, step4_keys=set(), silver_keys=set())
    assert validation["validation_status"] == "PASS_WITH_WARNINGS"
    assert any("tika total" in warning for warning in validation["warnings"])


def test_no_builtin_hash_in_selection_module() -> None:
    source = Path("backend/pali/translation/pilot_1000_selection.py").read_text(encoding="utf-8")
    assert "hash(" not in source
    assert "hashlib.sha256" in source


def test_apparatus_counts_use_step3h_importer(tmp_path: Path) -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<TEI.2><text><body><p rend="bodytext" n="1">Evaṃ accantadiṭṭhaṃ <note>antaṃ niṭṭhaṃ (sī.)</note>.</p></body></text></TEI.2>
"""
    xml_path = tmp_path / "romn" / "test.mul.xml"
    xml_path.parent.mkdir(parents=True)
    xml_path.write_text(xml, encoding="utf-8")
    artifact = parse_vri_xml(xml_path, source_path="romn/test.mul.xml", preserve_source_apparatus=False)
    inventory = artifact["segments"]
    counts, report = sel.compute_source_apparatus_counts(inventory, source_root=tmp_path)
    assert report["source_files_checked"] == 1
    assert counts[inventory[0]["stable_segment_key"]] == 1


def test_summary_mentions_gold_and_silver_policy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _result, _manifest, _validation, _run_manifest, paths = run_fixture_selection(monkeypatch, tmp_path)
    summary = (paths["out"] / "pilot_1000_v1_summary.md").read_text(encoding="utf-8")
    assert "gold accuracy is unavailable" in summary
    assert "silver canary remains advisory-only" in summary
