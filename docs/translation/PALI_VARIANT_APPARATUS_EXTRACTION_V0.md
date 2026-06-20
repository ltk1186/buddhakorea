# Pāli Variant Apparatus Extraction v0

## Purpose

Step 3F는 Pāli 300 pilot의 남은 `grammar_uncertain` / source-variant 의심 항목에 대해 VRI XML 내부의 `<note>` apparatus를 결정론적으로 추출하고 QA evidence로 연결하는 작업이다.

이번 단계는 번역 수정이 아니다. Gemini/API/LLM/Batch 호출, prompt/glossary/gold 수정, source XML 수정, parsed output 수정은 하지 않는다.

## Why Cross-Script Collation Was Deprecated

VipassanaTech/tipitaka-xml의 script별 파일은 독립 textual witness가 아니라 master source에서 전사 변환된 산출물일 가능성이 높다. 따라서 `romn/deva/sinh/thai/mymr` 비교는 source typo나 source variant 판정 도구로 적절하지 않다.

Step 3F에서는 cross-script collation을 구현하지 않는다. 대신 VRI XML 원문 내부의 `<note>` apparatus를 추출한다.

## Apparatus Notes Attest, Not Prove

VRI `<note>` apparatus는 변이독이 존재한다는 것을 증언(attest)한다. 이것은 main reading이 오류임을 자동으로 증명하지 않는다. VRI main text는 editor-selected reading으로 유지된다.

Any adoption of a variant reading requires a later reviewed decision with explicit provenance.

## Note Type Classification

`<note>`는 모두 변이독이 아니다. v0는 다음 유형을 구분한다.

- `variant`: alternative reading with witness siglum, e.g. `nettī (ka.)`
- `citation`: reference note, e.g. `ma. ni. 1.55`
- `peyyala`: abbreviation / ellipsis marker
- `editorial`: editorial explanation
- `unknown`: unresolved note type

Only `note_type=variant` and `is_variant_apparatus=true` records are used as variant apparatus evidence.

Citation detection happens before siglum detection so `ma. ni. 1.55` is not misclassified as Myanmar/Burmese `ma.` siglum.

## Sigla

Supported initial sigla:

- `sī.` = Sinhala
- `syā.` = Siamese / Thai
- `ka.` = unspecified manuscript group / “somewhere” style witness
- `pī.` = PTS
- `ma.` = Myanmar / Burmese

Unknown sigla are preserved instead of discarded.

`ka.` receives weaker evidence-strength metadata than named witnesses. This is only a hint and is not used as an automatic decision.

## Structural Attribution First

Structural paragraph/node attribution is preferred over lexical target-hint matching.

Attribution priority:

1. importer segment boundary / XML node path / paragraph identity
2. structural parent + source path + segment ordinal match
3. target-hint nearby window match
4. same source-path nearby note
5. no reliable mapping

Target-hint matching is fragile and should only be used as fallback evidence.

## Scope

v0 is not corpus-wide extraction.

It measures:

1. flagged subset: `review_required_after_classification=true` targets from the 300 pilot
2. full 300 pilot: apparatus-loss scale for all 300 parsed segments

The full 300 summary includes:

- segments with variant apparatus in source
- segments with variant apparatus missing from translation input
- segments with citation notes in source
- variant note records in 300 source scope
- citation note records in 300 source scope
- apparatus loss rate

This measurement prioritizes future importer preservation work. It is not a translation quality judgment.

## CLI

```bash
./venv/bin/python -m backend.pali.scripts.extract_variant_apparatus \
  --review-queue-reclassified data/qa_reports/pali/qa_report_300_live_salvaged_integrated/review_queue_reclassified.json \
  --findings data/qa_reports/pali/qa_report_300_live_salvaged_integrated/findings.json \
  --parsed data/reports/pali/pilot_300_batch/pilot_300_batch_parsed_salvaged.json \
  --source-root data/tipitaka-xml \
  --out data/qa_reports/pali/variant_apparatus_v0 \
  --max-targets 20 \
  --pretty
```

There is no network-fetch option.

## Outputs

```text
data/qa_reports/pali/variant_apparatus_v0/apparatus_premise_check.json
data/qa_reports/pali/variant_apparatus_v0/variant_apparatus.json
data/qa_reports/pali/variant_apparatus_v0/apparatus_qa_crosscheck.json
data/qa_reports/pali/variant_apparatus_v0/apparatus_findings.md
data/qa_reports/pali/variant_apparatus_v0/run_manifest.json
```

## Classification Names

Use:

```text
apparatus_attests_variant
```

Do not use any classification name that says the apparatus "confirms" a variant.
That wording overstates the evidence.

## #11 accantadiṭṭhaṃ Case

For `vri:romn:s0519m.mul:f43a9c761757`, the model flagged `accantadiṭṭhaṃ` as possibly related to `accantaniṭṭhaṃ`.

The source XML contains a nearby apparatus note:

```text
antaṃ niṭṭhaṃ (sī.)
```

This means #11 has an apparatus-attested variant involving `niṭṭhaṃ` in the Sinhala witness. It strongly supports source-variant review, but no automatic correction is applied.

```text
#11 has an apparatus-attested variant involving niṭṭhaṃ in the Sinhala witness.
This strongly supports a source-variant review, but no automatic correction is applied.
```

## Importer Note-Loss Finding

Current ingestion/translation pipeline appears to drop or exclude XML `<note>` apparatus from translation input. Future work should preserve `<note>` apparatus as structured metadata, separate from main text.

Do not silently merge note variants into main source text. Preserve as source apparatus metadata:

- `note_raw_text`
- `variant_text`
- `sigla`
- `anchor_text`
- `source_path`
- `xml_node_path`
- `char_offset`
- `stable_segment_key`

## Out of Scope

- corpus-wide apparatus extraction
- importer modification
- translation input modification
- source correction
- translation correction
- glossary update
- gold update
- TM
- reference table construction
- expert question writing
- response_schema micro-smoke
- 1,000 pilot

## Next Steps

1. Importer note preservation.
2. Apparatus-aware translation context experiment.
3. Reviewer-adopted variant provenance field.
