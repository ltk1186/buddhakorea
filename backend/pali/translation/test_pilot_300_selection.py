import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from backend.pali.scripts.build_pilot_300_manifest import (
    is_abhidhamma_definition,
    is_commentarial_discussion,
    is_glossary_risk,
    stable_json_sha256,
)
from backend.pali.translation.glossary import load_glossary


ROOT = Path(__file__).resolve().parents[3]
GLOSSARY = ROOT / "data/controlled_glossary.json"


def make_item(index, *, layer="mula", chunk="prose", length="medium", text="sabba dhamma", path=None, pitaka="sutta"):
    source_path = path or f"romn/s{index:04d}m.mul.xml"
    return {
        "stable_segment_key": f"seg-{index:04d}",
        "source_text_hash": f"hash-{index:04d}",
        "source_path": source_path,
        "source_file": Path(source_path).name,
        "literature_id": f"lit-{index:04d}",
        "canonical_ref": f"ref-{index:04d}",
        "sort_order": index,
        "text_layer": layer,
        "pitaka": pitaka,
        "nikaya": "TestNikaya",
        "chunk_type": chunk,
        "heading_path": [],
        "char_count": 40 if length == "short" else 140 if length == "medium" else 500,
        "length_bucket": length,
        "original_text": text,
        "normalized_text": text,
    }


def build_inventory():
    items = []
    index = 0
    for i in range(35):
        index += 1
        items.append(make_item(index, layer="tika", length="long", path=f"romn/s{i:04d}t.tik.xml", text="tassattho dī. ni. khandhānaṃ long prose", pitaka="sutta"))
    for i in range(35):
        index += 1
        items.append(make_item(index, layer="atthakatha", length="long", path=f"romn/s{i:04d}a.att.xml", text="ayamettha saṅkhāra long prose", pitaka="sutta"))
    for i in range(40):
        index += 1
        items.append(make_item(index, layer="mula", chunk="verse", length="medium", text="gāthā jā. uppalaṃ padumaṃ", pitaka="sutta"))
    for i in range(25):
        index += 1
        items.append(make_item(index, layer="mula", length="short", text="dī. ni. citation", pitaka="sutta"))
    for i in range(25):
        index += 1
        items.append(make_item(index, layer="mula", length="medium", text="khandhānaṃ manasikāro dhīro paṇḍito", pitaka="sutta"))
    for i in range(20):
        index += 1
        items.append(make_item(index, layer="mula", length="medium", text="katamo dhammo lakkhaṇa rasa", path=f"romn/abh{i:04d}m.mul.xml", pitaka="abhidhamma"))
    for i in range(20):
        index += 1
        items.append(make_item(index, layer="atthakatha", length="medium", text="adhippāyo ettha pana ācariyā", path=f"romn/s{i:04d}a.att.xml", pitaka="sutta"))
    for i in range(10):
        index += 1
        items.append(make_item(index, layer="mula", length="short", text="pe. peyyāla [broken", pitaka="sutta"))
    for layer, count in (("mula", 160), ("atthakatha", 120), ("tika", 90)):
        for i in range(count):
            index += 1
            length = ("short", "medium", "long")[i % 3]
            chunk = "verse" if i % 5 == 0 else "prose"
            path = f"romn/{'s' if layer == 'mula' else 'a' if layer == 'atthakatha' else 't'}{index:04d}.xml"
            items.append(make_item(index, layer=layer, chunk=chunk, length=length, text=f"ordinary source text {index}", path=path, pitaka="sutta"))
    return items


def write_inputs(tmp):
    inventory = {"items": build_inventory()}
    inventory_path = Path(tmp) / "inventory.json"
    inventory_path.write_text(json.dumps(inventory, ensure_ascii=False), encoding="utf-8")
    exclude_items = [
        {
            "stable_segment_key": f"seg-{i:04d}",
            "length_bucket": inventory["items"][i - 1]["length_bucket"],
            "chunk_type": inventory["items"][i - 1]["chunk_type"],
            "text_layer": inventory["items"][i - 1]["text_layer"],
        }
        for i in range(1, 76)
    ]
    exclude_path = Path(tmp) / "exclude.json"
    exclude_path.write_text(json.dumps({"items": exclude_items}, ensure_ascii=False), encoding="utf-8")
    gold_path = Path(tmp) / "gold.json"
    gold_path.write_text(json.dumps({"entries": [{"stable_segment_key": "seg-0076", "pool": "regression_gold"}]}), encoding="utf-8")
    return inventory_path, exclude_path, gold_path


def run_builder(tmp, *, env=None):
    inventory_path, exclude_path, gold_path = write_inputs(tmp)
    out = Path(tmp) / "out"
    return run_builder_with_paths(inventory_path, exclude_path, gold_path, out, env=env)


def run_builder_with_paths(inventory_path, exclude_path, gold_path, out, *, env=None):
    cmd = [
        sys.executable,
        "-m",
        "backend.pali.scripts.build_pilot_300_manifest",
        "--inventory",
        str(inventory_path),
        "--exclude-parsed",
        str(exclude_path),
        "--gold",
        str(gold_path),
        "--glossary",
        str(GLOSSARY),
        "--out",
        str(out),
        "--seed",
        "pilot_300_v1",
    ]
    subprocess.run(cmd, cwd=ROOT, check=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    manifest = json.loads((out / "pilot_300_v1_manifest.json").read_text(encoding="utf-8"))
    validation = json.loads((out / "pilot_300_v1_validation.json").read_text(encoding="utf-8"))
    return out, manifest, validation


class Pilot300SelectionTests(unittest.TestCase):
    def test_selection_outputs_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, manifest, validation = run_builder(tmp)
            self.assertTrue((out / "pilot_300_v1_manifest.json").exists())
            self.assertTrue((out / "pilot_300_v1_summary.md").exists())
            self.assertTrue((out / "pilot_300_v1_validation.json").exists())
            self.assertTrue(validation["valid"])
            self.assertEqual(manifest["summary"]["selected_count"], 300)
            self.assertEqual(manifest["summary"]["hard_count"], 100)
            self.assertEqual(manifest["summary"]["representative_count"], 200)

    def test_disjoint_and_unique_constraints(self):
        with tempfile.TemporaryDirectory() as tmp:
            _out, manifest, validation = run_builder(tmp)
            keys = [item["stable_segment_key"] for item in manifest["items"]]
            hard = {item["stable_segment_key"] for item in manifest["items"] if item["selection_group"] == "hard"}
            rep = {item["stable_segment_key"] for item in manifest["items"] if item["selection_group"] == "representative"}
            pilot75 = {f"seg-{i:04d}" for i in range(1, 76)}
            self.assertEqual(len(keys), len(set(keys)))
            self.assertFalse(hard & rep)
            self.assertFalse(set(keys) & pilot75)
            self.assertTrue(validation["checks"]["representative_excludes_hard_selected"]["pass"])

    def test_holdout_candidates_and_probe_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            _out, manifest, validation = run_builder(tmp)
            holdouts = [item for item in manifest["items"] if item["gold_candidate"]]
            self.assertGreaterEqual(len(holdouts), 15)
            self.assertLessEqual(len(holdouts), 20)
            for item in holdouts:
                self.assertEqual(item["pool_candidate"], "holdout_gold")
                self.assertTrue(item["do_not_use_for_tuning_until_reviewed"])
            self.assertTrue(validation["checks"]["heading_title_metadata_probe_cap"]["pass"])

    def test_same_seed_same_order_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            inventory_path, exclude_path, gold_path = write_inputs(tmp)
            _out1, manifest1, _validation1 = run_builder_with_paths(inventory_path, exclude_path, gold_path, Path(tmp) / "out1")
            _out2, manifest2, _validation2 = run_builder_with_paths(inventory_path, exclude_path, gold_path, Path(tmp) / "out2")
            self.assertEqual(
                [item["stable_segment_key"] for item in manifest1["items"]],
                [item["stable_segment_key"] for item in manifest2["items"]],
            )
            self.assertEqual(stable_json_sha256(manifest1), stable_json_sha256(manifest2))

    def test_pythonhashseed_does_not_change_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            inventory_path, exclude_path, gold_path = write_inputs(tmp)
            env1 = dict(os.environ)
            env2 = dict(os.environ)
            env1["PYTHONHASHSEED"] = "1"
            env2["PYTHONHASHSEED"] = "999"
            _out1, manifest1, _validation1 = run_builder_with_paths(inventory_path, exclude_path, gold_path, Path(tmp) / "out1", env=env1)
            _out2, manifest2, _validation2 = run_builder_with_paths(inventory_path, exclude_path, gold_path, Path(tmp) / "out2", env=env2)
            self.assertEqual(stable_json_sha256(manifest1), stable_json_sha256(manifest2))

    def test_hard_bucket_detectors_are_narrow(self):
        glossary = load_glossary(GLOSSARY)
        self.assertFalse(is_glossary_risk(make_item(1, text="safe ordinary fixedless term"), glossary))
        self.assertTrue(is_glossary_risk(make_item(2, text="saṅkhāra dhamma"), glossary))
        self.assertTrue(is_glossary_risk(make_item(3, text="khandhānaṃ"), glossary))
        self.assertFalse(is_abhidhamma_definition(make_item(4, text="iti ti", path="romn/abh0001m.mul.xml", pitaka="abhidhamma")))
        self.assertTrue(is_abhidhamma_definition(make_item(5, text="katamo dhammo", path="romn/abh0002m.mul.xml", pitaka="abhidhamma")))
        self.assertFalse(is_commentarial_discussion(make_item(6, layer="atthakatha", text="attho ti nāma")))
        self.assertTrue(is_commentarial_discussion(make_item(7, layer="atthakatha", text="tassattho ayamettha adhippāyo")))

    def test_representative_secondary_tags_and_inventory_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            _out, manifest, validation = run_builder(tmp)
            representatives = [item for item in manifest["items"] if item["selection_group"] == "representative"]
            self.assertTrue(any(item["secondary_tags"] for item in representatives))
            self.assertTrue(manifest["bucket_definition_source"]["bucket_classifier_applied_to_full_inventory"])
            self.assertTrue(manifest["bucket_definition_source"]["bucket_classifier_validated_against_75_artifact"])
            self.assertTrue(validation["checks"]["inventory_hash_present"]["pass"])


if __name__ == "__main__":
    unittest.main()
