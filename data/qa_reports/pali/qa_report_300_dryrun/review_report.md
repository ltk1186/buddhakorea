# Pāli QA Review Report v1.2

이 보고서는 local-only deterministic QA 산출물입니다. Prompt/API/DB/RAG/UI 작업을 수행하지 않았습니다.

## Summary

- execution mode: `single_run`
- regression mode: disabled
- total segments: 300
- schema valid / invalid: 300 / 0
- parse failed: 0
- Priority counts: {}
- auto-resolvable groups: 0
- human-needed groups: 0
- estimated human review minutes: 0
- source integrity gaps: {'missing_field:display_source_text': 300, 'missing_field:normalization_notes': 300, 'missing_field:raw_source_text': 300, 'missing_field:translation_source_text': 300}
- oracle availability: {'oracle_unavailable': 203, 'second_model_verifier_candidate': 97}
- run manifest: `data/qa_reports/pali/qa_report_300_dryrun/run_manifest.json`

Oracle 일치 = 정답 확정이 아니며, oracle 불일치 = 오역 확정이 아닙니다. 불일치는 review queue로 올리는 triage signal일 뿐입니다.

## Auto-Resolvable Summary

- none

## Human-Needed Queue

- none
## Representative Sample Package

### random
- `vri:romn:abh03t.tik:1c4cd2a168ad` · tika · prose · short
- `vri:romn:s0101t.tik:3ed5afb93a71` · tika · prose · long
- `vri:romn:s0305t.tik:f985488968a4` · tika · prose · long
- `vri:romn:s0402a.att:a4c3b70768ea` · atthakatha · prose · long
- `vri:romn:vin02a1.att:e5f5ffcdaed1` · atthakatha · prose · medium

### long
- `vri:romn:s0202t.tik:4d7f6125f3f5` · tika · prose · long
- `vri:romn:s0202t.tik:bcc8233c219b` · tika · prose · long
- `vri:romn:s0301t.tik:9b035b2c66f0` · tika · prose · long
- `vri:romn:s0402a.att:a4c3b70768ea` · atthakatha · prose · long
- `vri:romn:s0403t.tik:b8d8b0c2146c` · tika · prose · long

### verse
- `vri:romn:s0403t.tik:0b44a6389758` · tika · verse · medium
- `vri:romn:s0508a1.att:1233433564d1` · atthakatha · verse · short
- `vri:romn:s0508m.mul:f90c9806366a` · mula · verse · short
- `vri:romn:s0510m2.mul:6210bd21c95f` · mula · verse · short
- `vri:romn:vin02m4.mul:d49c727cc20c` · mula · verse · short

### tika
- `vri:romn:s0201t.tik:ad1304f9ee55` · tika · prose · medium
- `vri:romn:s0302t.tik:521aa5cd0ea3` · tika · prose · long
- `vri:romn:s0305t.tik:06cc4695c02b` · tika · prose · long
- `vri:romn:s0305t.tik:67c7836ad2e0` · tika · prose · long
- `vri:romn:vin01t2.tik:195c065cc5d3` · tika · prose · short

### title
- none

### citation_heavy
- `vri:romn:abh02a.att:99a218804bc5` · atthakatha · prose · long
- `vri:romn:s0101t.tik:0a9d7d33330f` · tika · prose · medium
- `vri:romn:s0103t.tik:93a37cfe8915` · tika · prose · medium
- `vri:romn:s0504a.att:f7749494d902` · atthakatha · verse · medium
- `vri:romn:s0519a.att:926904b81bfc` · atthakatha · prose · long

## Gold Results

### Holdout Correctness

- pass/fail/escalate: 0 / 0 / 0
- gold entries not present in this run: 9
- holdout_gold는 regression_gold와 합산하지 않습니다.

### Regression Canary

- current pass/fail/escalate: 0 / 0 / 0
- gold entries not present in this run: 9
- regression mode disabled: before/after verdict는 계산하지 않았습니다.

## Correctness Triage Candidates

- oracle_unavailable: 203
- second_model_verifier_candidate: 97

이번 단계에서는 CC0 parallel comparison, copyright eyes-only reference, second-model verifier live 호출을 실행하지 않습니다.
aṭṭhakathā / ṭīkā는 제외하지 않고 `oracle_unavailable`로 표시합니다.

## Mock QA Dry-Run Note

mock QA dry-run is not a translation quality signal. It does not evaluate doctrinal correctness, terminology quality, hallucination, or translation accuracy. It only validates parser/schema/report wiring.

gold empty is expected: current seed gold entries are disjoint from the 300 pilot selection.
