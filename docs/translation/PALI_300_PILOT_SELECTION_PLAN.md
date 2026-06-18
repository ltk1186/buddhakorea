# Pāli 300 Pilot Selection Plan

## Purpose

300 expanded pilot의 목적은 Gemini/API/LLM 호출 없이 후보 세그먼트 300개를 결정론적으로 고정하는 것이다. 이번 단계는 selection only이며, Batch JSONL 생성, Gemini Batch 제출, polling, parsing, QA Report CLI 실행, 최종 cost estimate를 하지 않는다.

300 pilot은 다음을 확인하기 위한 실험 설계다.

- 75 pilot에서 드러나지 않은 실패 유형.
- token/cost driver 후보.
- 장르별 난이도.
- QA Report CLI 실전성.
- 향후 holdout_gold 후보.

## Why Disjoint From 75 Pilot

300 pilot은 기존 75 pilot에서 이미 본 segment를 반복하지 않는다. `pilot_300 ∩ pilot_75 = ∅`이어야 한다.

이유:

- 75 pilot에서 노출된 prompt/glossary feedback에 오염되지 않은 새 실패 유형을 찾기 위해.
- 300 pilot의 holdout candidate를 만들기 위해.
- token/cost 분포가 기존 소표본에 과적합되지 않도록 하기 위해.

## Selection Order

선택 순서는 고정한다.

1. 75 pilot stable_segment_key 제외.
2. invalid, empty source, duplicate inventory entry 제외.
3. hard sample 100개 먼저 선택.
4. hard-selected key를 제외한 pool에서 representative 200개 선택.
5. 선택된 300개 중 holdout candidate 15~20개 표시.

hard를 먼저 뽑는 이유는 hard bucket이 희소하고 제약이 많기 때문이다. representative와 hard를 독립 추출하면 중복이 생겨 unique count가 300보다 작아질 수 있다. `selection_group`은 단일값이며, 한 segment는 `hard` 또는 `representative` 중 하나에만 속한다.

## Bucket Compatibility

`length_bucket`, `chunk_type`, `text_layer`는 75 pilot을 만들 때 사용한 classifier 또는 동일한 로직을 전체 inventory에 적용한다.

75 artifact는 새 300 segment의 bucket 값을 공급하는 데이터가 아니다. 75 artifact는 classifier가 기존 75 metadata를 재현하는지 확인하는 compatibility validation 용도로만 사용한다.

현재 구현은 `backend/pali/scripts/select_vri_translation_samples.py`의 `collect_candidates`와 `assign_length_buckets`를 재사용한다. 기존 함수를 찾을 수 없어 복원하는 경우에는 summary에 명시해야 한다.

## Hard Sample 100

Hard sample은 deterministic source-side detector만 사용한다.

권장 quota:

- `tika_long`: 20
- `atthakatha_long`: 15
- `verse`: 15
- `citation_heavy`: 15
- `glossary_risk`: 15
- `abhidhamma_definition`: 10
- `commentarial_discussion`: 5
- `source_text_anomaly_risk`: 3
- `long_compound_or_dense_prose`: 2

bucket 간 overlap이 있어도 primary `selection_bucket`은 하나만 부여한다. 이미 선택된 stable_segment_key는 다음 bucket에서 제외한다.

## Hard Bucket Detection Rules

`tika_long`: `text_layer == "tika"` and `length_bucket == "long"`.

`atthakatha_long`: `text_layer == "atthakatha"` and `length_bucket == "long"`.

`verse`: `chunk_type == "verse"`.

`citation_heavy`: source text에 citation marker가 하나 이상 등장한다. marker list는 코드 상수로 고정하고 summary에 기록한다.

`glossary_risk`: controlled glossary term이 탐지되더라도 모두 risk로 보지 않는다. 다음 중 하나 이상일 때만 발화한다.

- `context_variant`, `needs_human`, `cross_avoid`, `explicit_ambiguity` 타입 term.
- `cross_avoid` 관계가 선언된 term.
- `fixed` term이지만 `avoid_ko`가 정의된 term.

avoid_ko가 없는 안전한 fixed term만 등장하면 glossary_risk로 잡지 않는다. fuzzy matching, semantic matching, LLM-based term detection은 금지한다.

`abhidhamma_definition`: `pitaka == "abhidhamma"` 또는 `source_path`가 `abh` 계열이며, 강한 정의 marker가 있어야 한다. 다음 중 하나일 때만 발화한다.

- `katamo`, `katame`, `katamā`, `katamaṃ` 중 하나 이상.
- `lakkhaṇa`, `rasa`, `paccupaṭṭhāna`, `padaṭṭhāna` 중 둘 이상.

단독 `vuttaṃ`, 단독 `vuccati`, 단독 `ti`, 단독 `nāma`, 단독 `attho`는 발화하지 않는다. 이 규칙으로 quota가 부족해도 다시 느슨하게 만들지 않고, hard fallback으로 채우며 validation warning에 기록한다.

`commentarial_discussion`: `text_layer in {"atthakatha", "tika"}`이고 강한 주석 풀이 marker가 있어야 한다. 단독 `ti`, 단독 `attho`, 단독 `nāma`, 또는 long 조건만으로는 primary trigger가 아니다.

`source_text_anomaly_risk`: unmatched bracket, editorial marker, peyyāla marker, abnormal repeated punctuation, raw/normalized source mismatch처럼 source-side에서 사전 탐지 가능한 경우만 사용한다. 번역 후에만 알 수 있는 normalization issue는 추정하지 않는다.

`long_compound_or_dense_prose`: long prose에서 평균 token length가 높거나 punctuation density가 낮은 경우다. heuristic이며 summary에 기록한다.

## Representative Sample 200

Representative sample은 hard-selected key를 제외한 pool에서 선택한다.

대표 표본 200개 안에는 heading/title/metadata probe 5개를 먼저 확보한다. 따라서 기본 구조는 `195 stratified + 5 heading_title_probe`이다. probe item은 `selection_group = "representative"`, `selection_bucket = "heading_title_probe"`로 기록한다. 후보가 부족하면 가능한 만큼만 확보하고 validation warning을 남긴다. probe는 최대 10개를 넘기지 않는다.

목표 layer quota:

- `mula`: 67
- `atthakatha`: 67
- `tika`: 66

length target:

- short: 35%
- medium: 40%
- long: 25%

chunk_type은 prose 중심으로 한다. heading/title/metadata-ish는 전체 300개 중 5~10개 probe로 제한한다. heavy-only 300에서 heading/title에 과도한 예산을 쓰지 않기 위해서다.

Representative로 선택된 segment라도 hard detector에 걸리면 `secondary_tags`에 기록한다. 이 정보는 Step 3에서 대표 표본 안의 citation/glossary risk가 실제로 어떻게 나왔는지 비교하기 위해 필요하다.

## Holdout Candidate Policy

300개 중 15~20개를 holdout candidate로 표시한다. 이 단계에서 `data/gold_set.json`은 수정하지 않는다.

선호 순서:

1. `oracle_availability_hint == "cc0_parallel_candidate"`
2. `oracle_availability_hint == "second_model_verifier_candidate"`
3. `oracle_availability_hint == "oracle_unavailable"`

단, 이 선호는 절대 조건이 아니다. holdout은 다양한 layer/length/chunk를 포함해야 한다.

원칙:

- 기존 75 pilot과 겹치지 않는다.
- 기존 regression_gold seed와 겹치지 않는다.
- 너무 쉬운 title/number-only는 피한다.
- 너무 극단적인 hard case에만 치우치지 않는다.
- `do_not_use_for_tuning_until_reviewed = true`를 기록한다.

Step 3에서 glossary 후보를 harvest할 때 이 flag가 있는 segment는 근거로 사용하지 않는다.

## Oracle Availability Hint

각 item은 `oracle_availability_hint`를 가진다.

- `cc0_parallel_candidate`
- `copyright_eyes_only_reference_candidate`
- `second_model_verifier_candidate`
- `oracle_unavailable`
- `unknown`

이번 단계에서는 live oracle을 실행하지 않는다.

## Inventory Hash Provenance

Inventory cache도 결정론의 일부다.

Manifest provenance에는 다음을 기록한다.

- `inventory_cache_path`
- `inventory_item_count`
- `inventory_sha256`
- `inventory_generation_policy`

같은 inventory hash, 같은 exclude set, 같은 seed이면 같은 300 manifest가 나와야 한다. inventory가 재생성되면 hash가 달라질 수 있으므로 summary에 명시한다.

## Source Family Skew Note

Selection은 source-family 편중을 재조정하지 않는다. 다만 summary와 validation에는 `source_family_skew_note`를 남긴다. 특히 `s05` Khuddaka 계열은 verse/glossary-risk 집중 때문에 비중이 높을 수 있으므로 Step 2 cost estimate와 Step 3 findings에서 별도 보고해야 한다.

## Patch Traceability

마감 패치 이후 summary에는 `patched_from_manifest_sha256`, 새 `manifest_sha256`, `selection_content_sha256`를 함께 기록한다. 같은 seed와 같은 inventory cache에서 selection content hash가 유지되는지 확인한다.

## Output Files

산출물은 `data/pilot_sets/pali/` 아래에 둔다.

- `pilot_300_v1_manifest.json`
- `pilot_300_v1_summary.md`
- `pilot_300_v1_validation.json`

## Validation

Critical validation:

- selected count = 300
- hard count = 100
- representative count = 200
- hard/representative disjoint
- pilot 75와 disjoint
- stable_segment_key unique
- usable inventory present
- no Gemini/API/LLM call
- no Batch JSONL generated
- no DB write

## Next Step

다음 단계는 Cost Estimate + QA Dry-Run Plan이다. 이번 manifest만으로 Gemini Batch를 제출하지 않는다. 사용자 승인 전 300 Pilot Batch 제출 금지.
