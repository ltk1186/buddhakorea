# Pali Studio Translation Workflow Spec

Status: planning spec  
Scope: high-quality asynchronous translation workflow design  
Out of scope: LLM text generation API calls, bulk translation execution, DB migration, RAG, embedding, official price-based cost calculation

## 1. Model Strategy

Current strategic roles:

- Default production translation model: Gemini 3.1 Pro.
- Gold baseline / arbitration model: GPT-5.5.
- Optional future candidate: Gemini Flash-family models for lower-cost or faster workflows only, not as the default high-quality translation model.

Model names, availability, pricing, and rate limits are volatile. Do not hardcode provider model names or prices in application logic. Runtime model names should be injected through configuration or environment variables.

Recommended config shape:

```json
{
  "default_translation": {
    "provider": "gemini",
    "model": "CONFIGURED_AT_RUNTIME"
  },
  "arbitration": {
    "provider": "openai",
    "model": "CONFIGURED_AT_RUNTIME"
  },
  "fast_candidate": {
    "provider": "gemini",
    "model": "CONFIGURED_AT_RUNTIME",
    "role": "speed_or_cost_candidate"
  }
}
```

Before any production run, operators must re-check provider official documentation for:

- model name and API availability
- regional availability
- rate limits and batch limits
- input/output token accounting
- official pricing
- safety/policy constraints

## 2. Asynchronous Translation Workflow

Bulk translation must not use a synchronous request-response API path. It should run as an asynchronous job with independently retryable segment items.

High-level workflow:

1. Admin selects a source scope.
2. Admin selects target language and output profile.
3. Admin creates a translation job.
4. Background worker expands scope into segment items.
5. Worker processes items segment by segment.
6. Each item records provider/model/prompt/token/latency/error metadata.
7. Each successful item creates a new translation version.
8. Quality checks run after generation.
9. Flagged items become `needs_review` or are routed to arbitration.
10. Job aggregates progress, token usage, errors, retries, and quality flags.

Supported source scopes:

- one literature, e.g. `s0505m.mul`
- one commentary, e.g. `s0505a.att`
- all `mula`
- all `atthakatha`
- all `tika`
- one `nikaya`
- one `pitaka`
- custom list of `stable_segment_key` values

Initial output profile:

- `Korean Advanced`

Operational requirements:

- Provider rate limit must not fail the whole job.
- Timeout must not fail the whole job.
- JSON parse failure must be isolated to the item.
- Provider error must be retryable per item.
- Progress must track pending/running/succeeded/failed/retrying/needs_review/skipped/cancelled.
- Token usage should track estimates before execution and actual usage after execution.
- Quality flags should be item-level and job-level aggregatable.

## 3. Translation Job Lifecycle

No DB migration is implemented in this phase. The following are logical table candidates.

### 3.1 translation_jobs

Candidate fields:

| Field | Purpose |
| --- | --- |
| `id` | internal numeric primary key |
| `job_uuid` | external stable id |
| `source_commit` | VRI XML source commit used for segment identity |
| `scope_type` | `literature`, `text_layer`, `nikaya`, `pitaka`, `custom_segments` |
| `scope_value` | concrete scope value |
| `text_layer` | optional layer filter |
| `target_language` | initially `ko` |
| `output_profile` | initially `korean_advanced` |
| `default_provider` | e.g. Gemini provider key |
| `default_model` | configured default production model |
| `arbitration_provider` | e.g. OpenAI provider key |
| `arbitration_model` | configured arbitration model |
| `prompt_id` | prompt template id |
| `prompt_version` | immutable prompt version |
| `status` | job status enum |
| `total_items` | total item count |
| `pending_items` | pending count |
| `running_items` | running count |
| `succeeded_items` | succeeded count |
| `failed_items` | failed count |
| `needs_review_items` | review count |
| `estimated_input_tokens` | pre-run input estimate |
| `estimated_output_tokens` | pre-run output estimate |
| `actual_input_tokens` | provider-reported input tokens |
| `actual_output_tokens` | provider-reported output tokens |
| `estimated_cost_usd` | nullable until cost phase |
| `actual_cost_usd` | nullable until cost phase |
| `created_by` | admin user id |
| `created_at` | creation timestamp |
| `started_at` | first worker start |
| `finished_at` | terminal timestamp |
| `cancelled_at` | cancellation timestamp |
| `notes` | operator notes |

### 3.2 translation_job_items

Candidate fields:

| Field | Purpose |
| --- | --- |
| `id` | internal numeric primary key |
| `job_id` | parent job id |
| `segment_id` or `stable_segment_key` | canonical segment link |
| `source_text_hash` | source text version guard |
| `sort_order` | execution/display order |
| `status` | item status enum |
| `attempt_count` | retry attempts |
| `provider` | provider used for this attempt |
| `model` | model used for this attempt |
| `prompt_id` | prompt id used |
| `prompt_version` | prompt version used |
| `input_tokens` | actual or measured input tokens |
| `output_tokens` | actual output tokens |
| `total_tokens` | provider total if available |
| `latency_ms` | request latency |
| `error_code` | normalized error code |
| `error_message` | truncated operator-facing error |
| `quality_flags` | item quality flags |
| `translation_version_id` | created translation version |
| `created_at` | creation timestamp |
| `started_at` | processing start |
| `finished_at` | processing finish |
| `retry_after` | rate-limit/backoff timestamp |

Status enum:

- `pending`
- `running`
- `succeeded`
- `failed`
- `retrying`
- `needs_review`
- `cancelled`
- `skipped`

## 4. Translation Versioning Strategy

Long-term storage should not overwrite `Segment.translation`. Use a separate versioned structure such as `translation_versions` or `segment_translations`.

Candidate fields:

| Field | Purpose |
| --- | --- |
| `id` | internal numeric primary key |
| `segment_id` or `stable_segment_key` | canonical segment link |
| `source_text_hash` | source text version guard |
| `target_language` | initially `ko` |
| `output_profile` | e.g. `korean_advanced` |
| `provider` | provider that generated this version |
| `model` | model used |
| `prompt_id` | prompt template id |
| `prompt_version` | immutable prompt version |
| `translation_json` | structured output |
| `status` | version status enum |
| `quality_score` | optional machine/human score |
| `quality_flags` | detected flags |
| `review_status` | review workflow state |
| `reviewed_by` | reviewer user id |
| `reviewed_at` | review timestamp |
| `published_at` | publication timestamp |
| `superseded_by_id` | replacement version id |
| `created_at` | creation timestamp |

Status enum:

- `machine_draft`
- `machine_reviewed`
- `human_reviewed`
- `published`
- `deprecated`
- `rejected`

Policies:

- A segment can have multiple translation versions.
- Gemini 3.1 Pro and GPT-5.5 versions can coexist for the same segment.
- Arbitration creates a new version rather than overwriting the Gemini version.
- Site serving should prefer `published`.
- If no `published` version exists, MVP policy should be conservative: show machine drafts only in admin/review mode unless a separate public beta flag is enabled.
- Reader feedback should attach to both the `stable_segment_key` and the displayed `translation_version_id`.
- Retranslation creates a new version and links supersession metadata.

## 5. Korean Advanced Output Profile

Initial output profile: `korean_advanced`.

Do not include English translation fields in the initial profile. English can be a future output profile.

Candidate `translation_json`:

```json
{
  "literal_ko": "...",
  "natural_ko": "...",
  "terms": [
    {
      "pali": "...",
      "ko": "...",
      "gloss": "...",
      "note": "..."
    }
  ],
  "grammar_notes": [
    "..."
  ],
  "doctrinal_notes": [
    "..."
  ],
  "uncertainties": [
    "..."
  ],
  "quality_flags": [
    "..."
  ],
  "quality_flag_details": [
    {
      "flag": "too_short",
      "source": "local_validator",
      "severity": "warning",
      "message": "...",
      "evidence": {
        "ratio": 0.03
      }
    }
  ]
}
```

Field purposes:

- `literal_ko`: close Korean rendering that preserves Pali structure.
- `natural_ko`: polished Korean reading translation.
- `terms`: key Pali terms, Korean choices, glosses, and notes.
- `grammar_notes`: grammatical observations useful for review and future training data.
- `doctrinal_notes`: doctrinal or interpretive notes, especially for sensitive passages.
- `uncertainties`: explicit unresolved points, variant readings, or ambiguous grammar.
- `quality_flags`: compact compatibility list of review signals.
- `quality_flag_details`: future-compatible structured flag records with source, severity, message, and evidence.

## 6. Quality Flags and Arbitration Policy

Quality flags:

- `json_parse_failed`
- `schema_validation_failed`
- `empty_translation`
- `too_short`
- `too_long`
- `contains_untranslated_pali`
- `glossary_conflict`
- `doctrinal_risk`
- `grammar_uncertain`
- `low_confidence`
- `needs_human_review`
- `reader_feedback`
- `important_doctrinal_segment`

Quality flag sources:

- `local_validator`: deterministic application checks.
- `model_self_report`: the model reports uncertainty, doctrinal risk, or low confidence in its structured output.
- `human_admin`: admin/reviewer marks or overrides.
- `reader_feedback`: public reader feedback attached to a segment/version.

Recommended source ownership:

| Flag | Primary source |
| --- | --- |
| `json_parse_failed` | `local_validator` |
| `schema_validation_failed` | `local_validator` |
| `empty_translation` | `local_validator` |
| `too_short` | `local_validator` |
| `too_long` | `local_validator` |
| `contains_untranslated_pali` | `local_validator` |
| `glossary_conflict` | `local_validator` first, `human_admin` if manually marked |
| `doctrinal_risk` | `model_self_report` or `human_admin` |
| `grammar_uncertain` | `model_self_report` or `human_admin` |
| `low_confidence` | `model_self_report` or `human_admin` |
| `needs_human_review` | `local_validator`, `model_self_report`, or `human_admin` |
| `reader_feedback` | `reader_feedback` |
| `important_doctrinal_segment` | `human_admin` |

Future-compatible flag detail structure:

```json
{
  "flag": "contains_untranslated_pali",
  "source": "local_validator",
  "severity": "warning",
  "message": "Korean translation fields contain Pali diacritics.",
  "evidence": {
    "field": "natural_ko"
  }
}
```

Store both:

- `quality_flags`: compact query/filter array.
- `quality_flag_details`: audit trail and review context.

Arbitration triggers:

- Gemini output JSON schema validation failed.
- Translation length is far too short or too long relative to source and expected profile.
- Core Pali terms are left untranslated without explanation.
- `uncertainties` exceeds the configured threshold.
- `doctrinal_notes` include risk markers.
- Reader feedback is submitted.
- Admin marks the segment as important.
- Segment belongs to a high-difficulty scope, especially selected atthakatha/tika passages.
- Random QA sample selection.

Arbitration modes:

1. GPT-5.5 creates a new translation version.
2. GPT-5.5 evaluates Gemini output and creates revision suggestions.

MVP recommendation: start with "new translation version" because it is simpler to store and compare. Evaluation-and-revision can be added later.

## 7. Gemini 3.1 Pro countTokens Calibration Plan

Current Gemini corpus token estimates are local heuristic approximations. Before cost analysis, run sample-only Gemini 3.1 Pro `countTokens` calibration.

This phase may call Gemini `countTokens` only. It must not call text generation APIs.

Sampling strategy:

- Sample from `mula`, `atthakatha`, and `tika`.
- Use at least 30 samples per layer.
- Use 100-300 total samples.
- Include short, medium, and long segments.
- Include some largest segments.
- Cover prose and verse.
- Cover varied `heading_path`, `chunk_type`, `pitaka`, and `nikaya`.

Measurements:

- Official Gemini 3.1 Pro `countTokens` for source text only.
- Official Gemini 3.1 Pro `countTokens` for calibration prompt wrapper plus source text.
- Local heuristic estimate for the same samples.
- Ratio of official count to local estimate.

Confirmed model string:

- Marketing/model target: Gemini 3.1 Pro.
- `gemini-3.1-pro` returned `404 NOT_FOUND` for `v1beta` `countTokens`.
- Confirmed API model string: `models/gemini-3.1-pro-preview`.
- Confirmed supported methods include `generateContent`, `countTokens`, `createCachedContent`, and `batchGenerateContent`.
- This workflow uses only `countTokens` at this stage.

Sample artifact path:

```text
data/reports/pali/vri_translation_sample_candidates_<source_commit_short>.json
```

Calibration artifact path:

```text
data/reports/pali/gemini_token_calibration_<source_commit_short>.json
```

`data/reports/` is gitignored. The full `source_commit` must be stored inside the JSON artifact even when the filename uses a short commit.

API key:

- Read from the first available variable in this order:
  - `GEMINI_API_KEY`
  - `GOOGLE_API_KEY`
  - `GOOGLE_GENAI_API_KEY`
  - `PALI_GEMINI_API_KEY`
- The runner checks process environment first, then local `.env`, then `config/.env`.
- Never hardcode the key.
- Never write the key into logs or artifacts.
- `--dry-run` must work without an API key.
- Non-dry-run must fail clearly if no supported API key is available.

Existing Buddha Korea authentication note:

- The main RAG Gemini runtime defaults to Vertex AI through `ChatVertexAI`.
- The optional `GEMINI_PROVIDER=google_genai` route uses `GEMINI_API_KEY`.
- Pali Studio `gemini_client.py` tries `GEMINI_API_KEY` first, then falls back to Vertex AI if `GCP_PROJECT_ID` is configured.
- This calibration runner currently supports API-key countTokens only. Vertex AI countTokens support can be added later with an explicit auth mode such as `--auth-mode vertex --gcp-project-id ... --gcp-location ...`, but keeping this runner API-key-only reduces risk while we are measuring token counts rather than running production translation.

Implemented runner:

- `backend/pali/scripts/calibrate_gemini_tokens.py`

Dry-run:

```bash
./venv/bin/python backend/pali/scripts/calibrate_gemini_tokens.py \
  --samples data/reports/pali/vri_translation_sample_candidates_49bc869.json \
  --model models/gemini-3.1-pro-preview \
  --out data/reports/pali/gemini_token_calibration_dry_run_49bc869.json \
  --max-samples 10 \
  --dry-run \
  --pretty
```

Actual countTokens calibration:

```bash
GEMINI_API_KEY=... \
./venv/bin/python backend/pali/scripts/calibrate_gemini_tokens.py \
  --samples data/reports/pali/vri_translation_sample_candidates_49bc869.json \
  --model models/gemini-3.1-pro-preview \
  --out data/reports/pali/gemini_token_calibration_49bc869.json \
  --max-samples 150 \
  --timeout-seconds 60 \
  --max-retries 2 \
  --retry-backoff-seconds 2 \
  --pretty
```

Output top-level fields:

- `source_commit`
- `model`
- `generated_at`
- `sample_size`
- `successful_sample_count`
- `failed_sample_count`
- `sample_strategy`
- `dry_run`
- `input_samples_path`
- `api_used`
- `prompt_wrapper`
- `execution`

Aggregate fields:

- `local_estimate_total`
- `local_estimate_success_total`
- `official_source_text_only_total`
- `official_prompt_with_source_total`
- `ratio_by_text_layer`
- `ratio_by_chunk_type`
- `ratio_by_length_bucket`
- `ratio_by_pitaka`
- `ratio_by_nikaya`
- `recommended_source_correction_factor`
- `average_prompt_overhead_tokens`
- `median_prompt_overhead_tokens`
- `p90_prompt_overhead_tokens`

Diagnostics:

- `largest_ratio_outliers`
- `largest_prompt_overhead_samples`
- `failed_samples`
- `warnings`
- `fallback_notes`

Sample-level fields:

- `stable_segment_key`
- `source_path`
- `text_layer`
- `pitaka`
- `nikaya`
- `chunk_type`
- `length_bucket`
- `source_chars`
- `local_gemini_estimate_tokens`
- `official_source_text_only_tokens`
- `official_prompt_with_source_tokens`
- `source_ratio`
- `prompt_overhead_tokens`
- `status`
- `error_message`

Calibration prompt wrapper:

```text
You are translating Pāli Buddhist canonical and commentarial texts into Korean.

Return a JSON object matching the Korean Advanced schema:
{
  "literal_ko": "...",
  "natural_ko": "...",
  "terms": [],
  "grammar_notes": [],
  "doctrinal_notes": [],
  "uncertainties": [],
  "quality_flags": []
}

Do not add fields outside the schema.

Pāli source:
<<<
{source_text}
>>>
```

This wrapper is a calibration placeholder, not the final translation prompt. After Korean Advanced Prompt v1 is finalized, rerun `prompt_with_source_tokens` calibration.

Interpretation:

- `source_text_only_tokens`: official token count for the Pali segment text only.
- `prompt_with_source_tokens`: official token count for placeholder prompt plus source text.
- `source_ratio`: `official_source_text_only_tokens / local_gemini_estimate_tokens`.
- `prompt_overhead_tokens`: `official_prompt_with_source_tokens - official_source_text_only_tokens`.
- `recommended_source_correction_factor`: sample-based correction from local Gemini heuristic fallback to official Gemini countTokens.

Calibration result for source commit `49bc86914748589a2501b548cc6b3e97a8abe018`:

- Model: `models/gemini-3.1-pro-preview`.
- Sample size: 150.
- Successful samples: 150.
- Failed samples: 0.
- Local Gemini heuristic source tokens: 17,781.
- Official Gemini source text tokens: 30,337.
- Official Gemini prompt-with-source tokens: 46,237.
- Overall correction factor: 1.706147.
- Text-layer correction factors:
  - `mula`: 1.691869.
  - `atthakatha`: 1.713128.
  - `tika`: 1.712963.
- Chunk-type diagnostic ratios:
  - `prose`: 1.663608.
  - `verse`: 1.919229.
- Placeholder prompt overhead:
  - average: 106 tokens.
  - median: 106 tokens.
  - p90: 106 tokens.

Important diagnostic: verse samples have a higher correction ratio than prose samples. The default corpus correction still uses text-layer factors, but verse-heavy subsets should be reviewed separately.

Corrected source estimate report:

```bash
./venv/bin/python backend/pali/scripts/apply_gemini_token_calibration.py \
  --corpus-summary data/reports/pali/vri_romn_corpus_token_summary_49bc869.json \
  --calibration data/reports/pali/gemini_token_calibration_49bc869.json \
  --out data/reports/pali/vri_romn_corpus_token_summary_gemini_corrected_49bc869.json \
  --pretty
```

The corrected report applies text-layer correction factors by default and uses the overall factor only when a layer-specific factor is missing. Chunk-type and length-bucket ratios are diagnostics only.

The corrected source token estimate still excludes:

- final Korean Advanced Prompt v1 overhead;
- output tokens;
- context overhead;
- DPD hints;
- RAG context;
- retries;
- GPT arbitration;
- official price-based cost calculation.

Limitations:

- This is not a final cost calculation.
- It does not estimate output tokens.
- It does not include final prompt, glossary context, DPD hints, RAG context, retry rate, or arbitration overhead.
- It must not be used as official price-based total cost.

## 8. Pilot Translation Plan

Run a small pilot before any bulk translation.

Pilot scope:

- 50-100 segments.
- `s0505m.mul` subset.
- `s0505a.att` subset.
- Tika subset if available.
- Short, medium, and long segments.
- Prose and verse.

Pilot goals:

- Check Gemini 3.1 Pro Korean Advanced schema compliance.
- Evaluate `literal_ko` and `natural_ko` quality.
- Check whether `terms`, `grammar_notes`, and `doctrinal_notes` are useful and not excessive.
- Measure output token multiplier.
- Compare actual input/output usage against estimates.
- Measure quality flag rate.
- Estimate GPT-5.5 arbitration rate.

Pilot result artifact candidate:

```text
data/reports/pali/translation_pilot_<model>_<source_commit>.json
```

Suggested fields:

- `source_commit`
- `model`
- `output_profile`
- `sample_strategy`
- `sample_size`
- `schema_success_rate`
- `quality_flag_counts`
- `arbitration_candidate_rate`
- `input_tokens`
- `output_tokens`
- `output_token_multiplier`
- `review_notes`

## 9. Calibration and Pilot Sample Selector

Implemented local candidate selector:

- `backend/pali/scripts/select_vri_translation_samples.py`

The selector does not call LLM APIs. It parses VRI XML, stratifies canonical segments, and emits candidate JSON for later Gemini countTokens calibration and pilot translation.

Example:

```bash
SOURCE_COMMIT=$(git -C data/tipitaka-xml rev-parse HEAD)
SOURCE_COMMIT_SHORT=${SOURCE_COMMIT:0:7}

./venv/bin/python backend/pali/scripts/select_vri_translation_samples.py \
  --input-dir data/tipitaka-xml/romn \
  --include-layers mul,att,tik \
  --token-profiles config/pali_token_profiles.example.json \
  --source-commit "$SOURCE_COMMIT" \
  --calibration-size 150 \
  --pilot-size 75 \
  --out "data/reports/pali/vri_translation_sample_candidates_${SOURCE_COMMIT_SHORT}.json" \
  --pretty
```

Optional pilot scope narrowing:

```bash
./venv/bin/python backend/pali/scripts/select_vri_translation_samples.py \
  --input-dir data/tipitaka-xml/romn \
  --include-layers mul,att,tik \
  --source-commit "$SOURCE_COMMIT" \
  --pilot-source-paths romn/s0505m.mul.xml,romn/s0505a.att.xml,romn/s0519t.tik.xml \
  --out "data/reports/pali/vri_translation_sample_candidates_${SOURCE_COMMIT_SHORT}.json" \
  --pretty
```

The sample artifact path is intentionally under `data/reports/pali/`, which is gitignored.

Selection dimensions:

- `text_layer`: `mula`, `atthakatha`, `tika`.
- `length_bucket`: `short`, `medium`, `long`.
- `chunk_type`: `prose`, `verse`.
- `pitaka`.
- `nikaya`.
- largest segments per layer for calibration stress testing.

Output fields include:

- `candidate_pool_report`
- `calibration_samples`
- `pilot_samples`
- `stable_segment_key`
- `source_text_hash`
- `source_commit`
- `source_path`
- `text_layer`
- `pitaka`
- `nikaya`
- `chunk_type`
- `length_bucket`
- `token_estimates_by_profile`
- `heading_path`
- `original_text`

## 10. Cost Analysis Boundary

This document defines the cost-analysis structure only. It does not calculate official costs.

Separate token layers:

- `source_text_tokens`
- `prompt_overhead_tokens`
- `context_overhead_tokens`
- `estimated_output_tokens`

Required inputs for a later official cost analysis:

- Gemini 3.1 Pro official input token price.
- Gemini 3.1 Pro official output token price.
- GPT-5.5 official input token price.
- GPT-5.5 official output token price.
- Gemini countTokens calibration result.
- Pilot output token multiplier.
- Expected arbitration rate.
- Expected retry rate.

## 11. Implementation Roadmap

1. Keep improving VRI XML canonical segment identity and validation.
2. Add prompt template versioning for `korean_advanced`.
3. Add sample selector for calibration and pilot runs.
4. Run Gemini countTokens sample calibration.
5. Run 50-100 segment pilot with Gemini 3.1 Pro.
6. Validate output schema and quality flags.
7. Run GPT-5.5 arbitration on flagged pilot subset.
8. Decide publication policy for machine drafts.
9. Only then design DB migrations for jobs, job items, and translation versions.
10. Only after calibration and pilot, perform official price-based cost analysis.

## 12. Out of Scope

- Actual LLM API calls.
- Bulk translation execution.
- DB migration creation.
- RAG.
- Embedding.
- Official price-based cost calculation.
- Modifying existing `translate.py` or `gemini_client.py`.
- Making Gemini Flash-family models the default high-quality translator.
