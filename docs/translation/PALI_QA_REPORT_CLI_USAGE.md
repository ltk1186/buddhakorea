# Pāli QA Report CLI Usage

이 문서는 운영자가 QA report generator를 바로 실행하기 위한 복붙용 문서다. 이 CLI는 local-only 도구이며 Prompt 수정, Gemini/GPT/LLM 호출, DB write, RAG/embedding, UI 작업을 하지 않는다.

## 75 Baseline Single-Run

```bash
./venv/bin/python -m backend.pali.scripts.generate_qa_report \
  --parsed data/reports/pali/gemini_pilot_75_49bc869_prompt_qa_patch_v2_parsed.json \
  --gold data/gold_set.json \
  --glossary-qa data/reports/pali/translation_qa_v1_1_baseline_49bc869.json \
  --out data/reports/pali/qa_report_v1_2_pilot75
```

Single-run mode는 `--before-parsed`가 없을 때 사용한다. 현재 parsed result 하나의 risk profile, current gold pass/fail/escalate, review queue, source integrity gap, oracle availability summary를 생성한다. 이 모드에서는 regression verdict를 계산하지 않으며 `review_report.md`에 `regression mode disabled`가 표시된다.

## Before/After Regression

```bash
./venv/bin/python -m backend.pali.scripts.generate_qa_report \
  --before-parsed data/reports/pali/gemini_pilot_75_49bc869_prompt_v1_schemafix_parsed.json \
  --parsed data/reports/pali/gemini_pilot_75_49bc869_prompt_qa_patch_v2_parsed.json \
  --gold data/gold_set.json \
  --glossary-qa data/reports/pali/translation_qa_v1_1_baseline_49bc869.json \
  --out data/reports/pali/qa_report_v1_2_regression
```

Regression mode는 `--before-parsed`가 있을 때 사용한다. before와 after의 gold regression verdict를 `improved`, `worsened`, `neutral`, `escalate`로 계산한다. `worsened`는 Priority A review queue로 올라간다.

## 300 Pilot Template

```bash
./venv/bin/python -m backend.pali.scripts.generate_qa_report \
  --parsed <300_pilot_parsed.json> \
  --gold data/gold_set.json \
  --glossary-qa <300_qa_report.json> \
  --out data/reports/pali/qa_report_300_<run_id>
```

300/1,000/production shard report는 durable local path에 보관하되, commit 여부는 별도 판단한다. repo 비대화를 막기 위해 모든 대형 운영 report를 자동 commit 대상으로 보지 않는다.

## 출력 읽는 순서

1. `review_report.md`: 운영자가 먼저 읽는 요약 파일.
2. `review_queue.json`: 구조화된 검토 큐. 나중에 DB 또는 관리자 UI로 연결 가능해야 한다.
3. `run_manifest.json`: 재현용 manifest.

## Output Files

각 실행은 최소 세 파일을 만든다.

- `review_report.md`
- `review_queue.json`
- `run_manifest.json`

`run_manifest.json`에는 input path, input sha256, output path, prompt version, gold set version, QA infra version, script version, command line args, sample seed, execution mode가 들어간다.

## 자주 나는 오류

- parsed path 오류: `--parsed` 경로가 존재하는지 확인한다.
- gold set 없음: `--gold data/gold_set.json`을 지정한다.
- glossary QA report 없음: `--glossary-qa`는 필수다.
- source integrity field gap: 현재 pilot artifact에는 raw/display/translation source 분리 필드가 부족하므로 expected gap일 수 있다.
- reference registry 없음: fatal error가 아니다. oracle availability가 limited하게 표시된다.
- regression mode 누락: before/after 비교가 필요하면 `--before-parsed`를 반드시 지정한다.
- output directory overwrite: 같은 `--out`에 다시 실행하면 세 output 파일을 같은 내용으로 덮어쓴다. 같은 입력과 sample seed면 deterministic하게 동일 파일이 생성된다.

## run_manifest로 재실행

`run_manifest.json`의 `command_line_args` 배열을 확인한다. 그대로 shell command로 복사해서 재실행하면 같은 입력과 같은 sample seed로 동일 report가 생성된다.

## Sampling

`--sample-seed`가 있으면 해당 seed를 사용한다. 없으면 stable_segment_key 집합에서 `hashlib.sha256`으로 deterministic seed를 만든다. Regression mode에서는 before/after stable_segment_key 교집합을 사용하므로 같은 segment 집합을 비교한다.

내장 `hash()`는 사용하지 않는다.
