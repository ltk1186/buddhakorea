# Pāli Variant Apparatus Extraction v0

## Purpose

This report extracts VRI XML `<note>` apparatus evidence for the 300 pilot QA subset. It does not modify source text, translations, parsed output, prompts, glossary, or gold sets.

## Why Cross-Script Collation Was Deprecated

Script variants are generated from a master source and are not treated as independent witnesses for source-variant detection.

## Premise Check

- cross_script_collation_deprecated: `True`
- importer loss location: `extract_main_text excludes note elements; exact downstream loss location not_determined`

## Source Files Checked

- source files checked: 105
- note records extracted: 14609

## Note Counts and Sigla Counts

- sigla counts: {'ka': 4261, 'pī': 4036, 'syā': 5643, 'sī': 6540}
- note type counts: {'citation': 597, 'editorial': 99, 'unknown': 671, 'variant': 13242}

## 300 Pilot Flagged Target Summary

- target count: 12
- apparatus_attests_variant: 1
- apparatus_has_variant_nearby: 1
- no_apparatus_variant: 10
- apparatus_extraction_missing_source: 0
- apparatus_attribution_failed: 0

## Full 300 Apparatus-Loss Summary

- total segments: 300
- segments with variant apparatus in source: 10
- segments with variant apparatus missing from translation input: 9
- segments with citation notes in source: 1
- variant note records in 300 source scope: 12
- citation note records in 300 source scope: 1
- apparatus loss rate: 0.9

## #11 accantadiṭṭhaṃ Case Study

- stable_segment_key: `vri:romn:s0519m.mul:f43a9c761757`
- classification: `apparatus_attests_variant`
- evidence: Source note attests a variant reading 'antaṃ niṭṭhaṃ (sī.)' near target accantadiṭṭhaṃ.
- interpretation: #11 has an apparatus-attested variant involving `niṭṭhaṃ` in the Sinhala witness. This strongly supports a source-variant review, but no automatic correction is applied.

## Apparatus Cross-Check Results

| stable_segment_key | target_hint | classification |
| --- | --- | --- |
| `vri:romn:s0519m.mul:f43a9c761757` | `accantadiṭṭhaṃ` | `apparatus_attests_variant` |
| `vri:romn:abh03m11.mul:4ab6e93ef3c3` | `nanabhāvanāya` | `no_apparatus_variant` |
| `vri:romn:s0302t.tik:75cb6eb45b34` | `Tassāti pāṭhassa` | `no_apparatus_variant` |
| `vri:romn:vin02a2.att:bfbd7f00efd4` | `Jiridanti` | `no_apparatus_variant` |
| `vri:romn:abh03t.tik:5ce9d8787e18` | `paṭiloma` | `no_apparatus_variant` |
| `vri:romn:s0102t.tik:691b6cc86c16` | `ettha panā` | `no_apparatus_variant` |
| `vri:romn:s0201t.tik:cfd6c2db8704` | `samāna` | `no_apparatus_variant` |
| `vri:romn:vin02a1.att:b56ffa453013` | `dukkaṭa` | `no_apparatus_variant` |
| `vri:romn:s0403t.tik:0b44a6389758` | `` | `no_apparatus_variant` |
| `vri:romn:s0513m.mul:545a4ef14103` | `` | `no_apparatus_variant` |
| `vri:romn:s0514m.mul:88650af1ca41` | `` | `apparatus_has_variant_nearby` |
| `vri:romn:vin01t2.tik:46bf2dc6b638` | `` | `no_apparatus_variant` |

## Importer Note-Loss Finding

Current ingestion/translation pipeline appears to drop or exclude XML `<note>` apparatus from translation input. Future work should preserve `<note>` apparatus as structured metadata, separate from main text.

## Caveat: Apparatus Evidence Is Not Automatic Correction

Apparatus notes attest variant readings; they do not automatically prove that the main reading is erroneous. The VRI main text remains the editor-selected reading. Any adoption of a variant reading requires a later reviewed decision with explicit provenance.

No automatic correction was applied. `auto_modify_translation=false` and `auto_modify_source=false` remain in the cross-check output.

## Upstream Recommendation

Preserve note apparatus as source metadata fields: `note_raw_text`, `variant_text`, `sigla`, `anchor_text`, `source_path`, `xml_node_path`, `char_offset`, and `stable_segment_key`.

Do not silently merge note variants into main source text.

## Next Steps

1. Importer note preservation.
2. Apparatus-aware translation context experiment.
3. Reviewer-adopted variant provenance field.
