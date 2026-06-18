# Pāli 300 Pilot Selection Manifest v1

## Purpose

이 산출물은 Gemini/API/LLM 호출 없이 300 expanded pilot 후보 300개를 결정론적으로 고정한다. 이 manifest만으로 Gemini Batch를 제출하지 않는다.

## Input Inventory

- inventory cache: `data/pilot_sets/pali/pilot_300_v1_inventory_cache_49bc869.json`
- inventory item count: 203594
- inventory sha256: `0cf74813283ee50ea649dcd14f52eb13fd37f98ca46084cd96c0a3ac09c328ca`
- inventory generated for this run: False

## Source Provenance

- source repo: VipassanaTech/tipitaka-xml or local equivalent
- source commit: 49bc86914748589a2501b548cc6b3e97a8abe018
- source root: data/tipitaka-xml

## Excluded 75 Pilot Count

- excluded pilot 75 count: 75
- source: `data/reports/pali/gemini_pilot_75_49bc869_prompt_qa_patch_v2_parsed.json`

## Selection Policy

- hard sample: 100
- representative sample: 200
- total: 300
- selection only; no Gemini Batch, no Batch JSONL, no final cost estimate.

## Selection Order

1. exclude 75 pilot keys
2. select hard 100 first
3. select representative 200 from remaining pool
4. mark holdout candidates

## Distribution Tables

- by text_layer: {'atthakatha': 112, 'mula': 91, 'tika': 97}
- by length_bucket: {'long': 113, 'medium': 102, 'short': 85}
- by chunk_type: {'prose': 224, 'verse': 76}
- by selection_bucket: {'abhidhamma_definition': 10, 'atthakatha_long': 15, 'citation_heavy': 15, 'commentarial_discussion': 5, 'glossary_risk': 15, 'long_compound_or_dense_prose': 2, 'representative_stratified': 200, 'source_text_anomaly_risk': 3, 'tika_long': 20, 'verse': 15}
- by source family/path prefix: {'abh01': 8, 'abh02': 13, 'abh03': 26, 'e01': 7, 's01': 23, 's02': 22, 's03': 24, 's04': 21, 's05': 117, 'vin01': 22, 'vin02': 17}

## Hard Bucket Detection Rules

- `tika_long`: text_layer == tika and length_bucket == long
- `atthakatha_long`: text_layer == atthakatha and length_bucket == long
- `verse`: chunk_type == verse
- `citation_heavy`: source_text contains one or more citation markers: ['dī. ni.', 'ma. ni.', 'saṃ. ni.', 'aṅ. ni.', 'khu. pā.', 'dha. pa.', 'udā.', 'itivu.', 'jā.', 'mahāva.', 'cūḷava.', 'visuddhi.', 'aṭṭha.', 'ṭī.', 'abhidhamma']
- `glossary_risk`: controlled glossary term is context_variant/needs_human/cross_avoid, or fixed with avoid_ko
- `abhidhamma_definition`: abhidhamma source plus specific definition markers; ti/nāma/attho alone do not trigger
- `commentarial_discussion`: atthakatha/tika plus strong discussion markers; long alone does not trigger
- `source_text_anomaly_risk`: source-side bracket/editorial/peyyāla/repeated punctuation/raw-normalized anomaly
- `long_compound_or_dense_prose`: long prose with high average token length or low punctuation dense prose

## Holdout Candidate List

- `vri:romn:e0102n.mul:bbe350bc990e` · mula · short · prose
- `vri:romn:s0103m.mul:3181017eacbc` · mula · short · prose
- `vri:romn:s0404m1.mul:370c63d8466c` · mula · medium · prose
- `vri:romn:e0101n.mul:1c6cd91e9a2a` · mula · medium · prose
- `vri:romn:abh03m10.mul:cf9f1a15cc86` · mula · medium · prose
- `vri:romn:abh03m6.mul:cd98d09085dc` · mula · medium · prose
- `vri:romn:s0304m.mul:af0991c6383c` · mula · long · prose
- `vri:romn:abh02m.mul:c8caabe29ead` · mula · long · prose
- `vri:romn:s0102m.mul:6a72ce6bb12a` · mula · long · prose
- `vri:romn:abh03m4.mul:b43a304ba12f` · mula · long · prose
- `vri:romn:vin02m1.mul:0d7d37de4c19` · mula · long · prose
- `vri:romn:abh03m6.mul:1faf6330366a` · mula · long · prose
- `vri:romn:s0514a1.att:9ea186253995` · atthakatha · short · verse
- `vri:romn:s0502a.att:5760bcbd5256` · atthakatha · short · verse
- `vri:romn:s0514a1.att:1948090bd6f5` · atthakatha · medium · verse
- `vri:romn:s0508a1.att:8b9574445272` · atthakatha · long · prose
- `vri:romn:vin02t.tik:4b896ba967ee` · tika · short · prose
- `vri:romn:abh02t.tik:7eaccfe9d5a0` · tika · short · prose
- `vri:romn:s0201t.tik:732e56d7e791` · tika · medium · prose
- `vri:romn:vin01t2.tik:46bf2dc6b638` · tika · medium · prose

## Hard Bucket Examples

- `vri:romn:s0403t.tik:b8d8b0c2146c` · tika_long · secondary=['tika_long', 'long_compound_or_dense_prose']
- `vri:romn:s0402t.tik:48d47702d5bf` · tika_long · secondary=['tika_long', 'long_compound_or_dense_prose']
- `vri:romn:abh02t.tik:38d55f5aef7a` · tika_long · secondary=['tika_long', 'glossary_risk', 'abhidhamma_definition', 'long_compound_or_dense_prose']
- `vri:romn:s0305t.tik:06cc4695c02b` · tika_long · secondary=['tika_long', 'long_compound_or_dense_prose']
- `vri:romn:s0201t.tik:1b5b6749bb28` · tika_long · secondary=['tika_long', 'long_compound_or_dense_prose']
- `vri:romn:vin01t1.tik:850b89bc875e` · tika_long · secondary=['tika_long', 'glossary_risk']
- `vri:romn:s0203t.tik:58781e65df6a` · tika_long · secondary=['tika_long', 'citation_heavy', 'long_compound_or_dense_prose']
- `vri:romn:vin01t2.tik:43fc549f3dfc` · tika_long · secondary=['tika_long']
- `vri:romn:s0202t.tik:4d7f6125f3f5` · tika_long · secondary=['tika_long', 'commentarial_discussion', 'long_compound_or_dense_prose']
- `vri:romn:s0302t.tik:521aa5cd0ea3` · tika_long · secondary=['tika_long', 'commentarial_discussion', 'long_compound_or_dense_prose']

## Heading/Title/Metadata Probe Count

- probe count: 0

## Warnings

- none

## Holdout Contamination Rule

`do_not_use_for_tuning_until_reviewed == true`인 segment는 Step 3 glossary 후보 harvest 근거로 사용하지 않는다.

## Next Step

다음 단계는 Cost Estimate + QA Dry-Run Plan이다. 사용자 승인 전 300 Pilot Batch 제출 금지.
