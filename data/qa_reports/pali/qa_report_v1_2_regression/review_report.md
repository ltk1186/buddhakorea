# Pāli QA Review Report v1.2

이 보고서는 local-only deterministic QA 산출물입니다. Prompt/API/DB/RAG/UI 작업을 수행하지 않았습니다.

## Summary

- execution mode: `regression`
- regression mode: enabled
- total segments: 75
- schema valid / invalid: 75 / 0
- parse failed: 0
- Priority counts: {'B': 5, 'C': 1}
- auto-resolvable groups: 1
- human-needed groups: 5
- estimated human review minutes: 15
- source integrity gaps: {'missing_field:display_source_text': 75, 'missing_field:normalization_notes': 75, 'missing_field:raw_source_text': 75, 'missing_field:translation_source_text': 75}
- oracle availability: {'oracle_unavailable': 50, 'second_model_verifier_candidate': 25}
- run manifest: `data/qa_reports/pali/qa_report_v1_2_regression/run_manifest.json`

Oracle 일치 = 정답 확정이 아니며, oracle 불일치 = 오역 확정이 아닙니다. 불일치는 review queue로 올리는 triage signal일 뿐입니다.

## Auto-Resolvable Summary

- allowed_parenthetical_pali: 14

## Human-Needed Queue

### B · grammar_uncertain:vri:romn:abh03t.tik:6fbb7ff462ce

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:abh03t.tik:6fbb7ff462ce']
- signals: ['grammar_uncertain']
- suggested_action: human_review
- estimated_review_minutes: 3
- review_tier: tier_1_operator

### B · reference_only_gold:gold-v0-abbokinna-001

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:e0104n.att:ce9536156dac']
- signals: ['reference_only_gold']
- suggested_action: manual_reference_or_expert_review_if_high_leverage
- estimated_review_minutes: 3
- review_tier: tier_1_operator

### B · reference_only_gold:gold-v0-anulomika-khanti-001

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:e0103n.att:0f1e7b16a8fb']
- signals: ['reference_only_gold']
- suggested_action: manual_reference_or_expert_review_if_high_leverage
- estimated_review_minutes: 3
- review_tier: tier_1_operator

### B · reference_only_gold:gold-v0-long-tika-001

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0402t.tik:af9f6dc82fdf']
- signals: ['reference_only_gold']
- suggested_action: manual_reference_or_expert_review_if_high_leverage
- estimated_review_minutes: 3
- review_tier: tier_1_operator

### B · reference_only_gold:gold-v0-untranslated-pali-001

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:vin01t1.tik:b9c1a89b49aa']
- signals: ['reference_only_gold']
- suggested_action: manual_reference_or_expert_review_if_high_leverage
- estimated_review_minutes: 3
- review_tier: tier_1_operator

## Representative Sample Package

### random
- `vri:romn:abh01t.tik:411fd5bc316b` · tika · verse · short
- `vri:romn:abh03m10.mul:095ce215bd0f` · mula · prose · long
- `vri:romn:s0102m.mul:d17d0ca3f887` · mula · verse · short
- `vri:romn:s0401m.mul:ec6609ed1b0a` · mula · prose · short
- `vri:romn:s0403a.att:d18c5e2dddeb` · atthakatha · prose · medium

### long
- `vri:romn:e0101n.mul:462c11938bc6` · mula · prose · long
- `vri:romn:s0401a.att:de09c6c7fbd8` · atthakatha · prose · long
- `vri:romn:s0404m2.mul:2677066d018a` · mula · prose · long
- `vri:romn:s0519t.tik:fa9495f8097d` · tika · verse · long
- `vri:romn:vin01t1.tik:b9c1a89b49aa` · tika · prose · long

### verse
- `vri:romn:e0101n.mul:c5a54ec9b23a` · mula · verse · short
- `vri:romn:e0101n.mul:f81c59d325f2` · mula · verse · medium
- `vri:romn:e0103n.att:0f1e7b16a8fb` · atthakatha · verse · short
- `vri:romn:s0403m3.mul:dae89c16d905` · mula · verse · medium
- `vri:romn:s0519t.tik:fa9495f8097d` · tika · verse · long

### tika
- `vri:romn:abh02t.tik:44f69334002c` · tika · prose · long
- `vri:romn:abh03t.tik:6fbb7ff462ce` · tika · prose · medium
- `vri:romn:s0201t.tik:8e951c4f787c` · tika · verse · long
- `vri:romn:s0402t.tik:64a0534991bb` · tika · prose · medium
- `vri:romn:vin01t1.tik:b9c1a89b49aa` · tika · prose · long

### title
- none

### citation_heavy
- `vri:romn:abh02a.att:24195e117aef` · atthakatha · verse · short
- `vri:romn:e0101n.mul:f81c59d325f2` · mula · verse · medium
- `vri:romn:s0201t.tik:8e951c4f787c` · tika · verse · long
- `vri:romn:s0517a.att:fce7fb5aa3b1` · atthakatha · verse · long
- `vri:romn:vin01t1.tik:b9c1a89b49aa` · tika · prose · long

## Gold Results

### Holdout Correctness

- pass/fail/escalate: 0 / 0 / 0
- holdout_gold는 regression_gold와 합산하지 않습니다.

### Regression Canary

- verdict counts: {'escalate': 4, 'improved': 1, 'neutral': 4, 'worsened': 0}

## Correctness Triage Candidates

- oracle_unavailable: 50
- second_model_verifier_candidate: 25

이번 단계에서는 CC0 parallel comparison, copyright eyes-only reference, second-model verifier live 호출을 실행하지 않습니다.
aṭṭhakathā / ṭīkā는 제외하지 않고 `oracle_unavailable`로 표시합니다.
