# Pāli QA Findings Classifier Integration

## Purpose

Step 3C/3D에서 검증한 Pāli QA Findings Classifier v1을 main QA pipeline에 통합한다. 목표는 `contains_untranslated_pali`의 false positive를 운영자가 매번 수동으로 정리하지 않도록, raw QA queue 위에 deterministic refinement layer를 자동으로 실행하는 것이다.

이 통합은 번역문, parsed payload, prompt, glossary, gold set을 수정하지 않는다. 외부 API, Gemini, second-model judge, Batch 호출도 하지 않는다.

## Raw Human-Needed vs Effective Human-Needed

Raw human-needed는 기존 QA report generator가 만든 원본 review queue 기준 사람 검토 대상 수다.

Effective human-needed는 classifier가 `contains_untranslated_pali`를 allowed display pattern과 strict review signal로 분해한 뒤에도 여전히 사람이 봐야 하는 수다.

두 값은 항상 함께 보존한다. `classifier=off` 또는 `classifier=auto` skip인 경우에도 `effective_human_needed`는 downstream 소비자를 위해 항상 존재하며, 이때 값은 raw human-needed와 같다.

## contains_untranslated_pali False Positive

300 pilot에서 다수의 `contains_untranslated_pali`는 실제 미번역이 아니라 다음 유형이었다.

- 한국어 번역 뒤 괄호 안 Pāli lemma 병기
- 주석/복주석에서 문법 lemma를 설명 대상으로 인용
- Pāli 구절을 인용한 뒤 한국어 설명이 뒤따르는 경우
- `terms[]`에 이미 설명된 기술어

classifier는 이 signal을 다음 sub-signal로 나눈다.

- `pali_parenthetical_allowed`
- `pali_grammar_quote_allowed`
- `pali_lemma_discussion_allowed`
- `pali_proper_name_or_title_allowed`
- `terms_explained_pali_allowed`
- `possible_untranslated_pali_strict`
- `grammar_uncertain_retained`

## Strict Untranslated Pāli by Exclusion

classifier는 run/signal worst-case rule을 사용한다. 한 세그먼트에 허용 가능한 Pāli 병기와 허용되지 않은 bare Pāli run이 함께 있으면, 세그먼트 전체를 auto-accept하지 않는다.

`possible_untranslated_pali_strict`는 다음 허용 규칙 어디에도 덮이지 않는 Pāli/roman run이 있을 때만 남는다.

- parenthetical Pāli after Korean translation
- grammar quote
- lemma discussion
- proper-name or title candidate
- terms explained Pāli

## grammar_uncertain Policy

`grammar_uncertain`은 deterministic classifier가 자동 통과시키지 않는다.

- `grammar_uncertain_auto_accepted`는 항상 `0`이어야 한다.
- `grammar_uncertain`이 있는 item은 `review_required_after_classification=true`로 남는다.
- classifier가 제공하는 `grammar_uncertain_hint`는 정렬용 힌트이며 correctness decision이 아니다.

## Output Files

`generate_qa_report`가 classifier를 실행하면 QA output directory에 다음 raw 파일과 classifier 파일이 함께 생성된다.

Raw QA output:

- `review_report.md`
- `review_queue.json`
- `run_manifest.json`

Classifier output:

- `findings.json`
- `findings.md`
- `review_queue_reclassified.json`
- `pali_qa_pattern_decisions_v1.json`

`review_queue.json`은 raw queue로 보존한다. reclassified queue로 덮어쓰지 않는다.

## CLI Modes

`generate_qa_report`와 `run_pilot_300_batch --mode qa`는 다음 옵션을 지원한다.

```bash
--pali-findings-classifier auto
--pali-findings-classifier on
--pali-findings-classifier off
```

`auto`는 기본값이다. parsed payload와 review queue가 있고, `contains_untranslated_pali` 또는 `grammar_uncertain` signal이 있으면 classifier를 실행한다. 관련 signal이 없으면 skip하고 `effective_human_needed=raw_human_needed`를 기록한다.

`on`은 classifier를 반드시 실행한다. 필요한 입력이 없으면 QA run을 실패시킨다.

`off`는 classifier를 실행하지 않는다. raw QA output만 생성하고 `effective_human_needed=raw_human_needed`를 기록한다.

## run_manifest Metadata

`run_manifest.json`에는 다음 정보가 기록된다.

```json
{
  "qa_summary": {
    "raw_human_needed": 79,
    "effective_human_needed": 12
  },
  "pali_findings_classifier": {
    "mode": "auto",
    "enabled": true,
    "api_network_calls": 0,
    "translation_mutation": false,
    "prompt_glossary_gold_mutation": false,
    "effective_human_needed": 12
  }
}
```

## Pattern Decisions Are Output Records

`pali_qa_pattern_decisions_v1.json` is an output record of the rules applied in this run. It is not an input configuration file. Editing this file does not change classifier behavior. Classifier behavior is currently defined in versioned code.

Future note: If the 1,000 pilot reveals many new allowed Pāli patterns, rules may later be externalized into a versioned data/config file. For Step 3E, rules remain code-defined and this JSON is only an output record.

## Correctness Caveat

Auto-allowed items are flag-level false positives, not certified-correct translations. Translation correctness remains tracked separately through gold/holdout regression, sampling, oracle comparison where available, and later human/expert review.

This caveat is present in both `findings.md` and the top-level `correctness_caveat` field of `findings.json`.

## 300 Pilot Baseline Numbers

The Step 3C/3D standalone classifier produced:

- raw human-needed: `79`
- effective human-needed: `12`
- contains_untranslated_pali before: `73`
- auto-allowed: `67`
- possible_untranslated_pali_strict: `0`
- total Pāli runs detected: `732`
- covered Pāli runs: `732`
- uncovered Pāli runs: `0`
- grammar_uncertain_auto_accepted: `0`
- grammar_uncertain_retained_for_review: `11`
- recommended sample size: `10`

Integrated output for the same inputs must match these core classifier results.

## Output Folder Collision

Step 3C/3D standalone classified outputs are preserved in their own output directory. Step 3E integrated outputs must use a separate QA output directory unless the user explicitly chooses the same directory.

Recommended local confirmation output:

```text
data/qa_reports/pali/qa_report_300_live_salvaged_integrated
```

Do not overwrite:

```text
data/qa_reports/pali/qa_report_300_live_salvaged_classified
```

## Sampling Guard

Auto-allowed items should still be sampled in later batches.

Recommended guard:

- `auto_allowed_count <= 100`: sample `10`
- `auto_allowed_count > 100`: sample `max(10, ceil(auto_allowed_count * 0.05))`, capped at `50`

Sampling should be stratified by decision, subsignal, and text layer.

## Next Steps

1. Cross-script collation v0.
2. grammar_uncertain findings harvest.
3. response_schema micro-smoke before the 1,000 pilot.
4. second-model verifier only after deterministic false positives are reduced.
