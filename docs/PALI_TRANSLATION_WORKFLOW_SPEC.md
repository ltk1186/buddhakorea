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

### 5.1 Korean Advanced Prompt v1

Implemented prompt skeleton:

- `backend/pali/translation/prompts.py`
- prompt id: `korean_advanced`
- prompt version: `korean_advanced_v1_schemafix`
- default model: `models/gemini-3.1-pro-preview`

Purpose:

- Convert one canonical VRI Pāli XML segment into Korean Advanced JSON.
- Work with Gemini Batch API request JSONL.
- Keep output limited to Korean translation JSON.
- Exclude English translation fields.
- Preserve segment identity in the prompt only through minimal context.
- Keep source path, API keys, internal cost data, and credentials out of the prompt.

Prompt v1 translation philosophy:

- Be faithful to the Pāli source.
- Clearly separate literal translation and natural translation.
- `literal_ko` preserves source structure, key predicates, case relations, and word order as far as Korean allows.
- `natural_ko` reads naturally in Korean while staying conservative about the source meaning.
- Do not insert doctrinal explanation into `literal_ko` or `natural_ko`.
- Limited reader-friendly Buddhist vocabulary is allowed in `natural_ko`.
- Do not reinterpret early Buddhist / Theravāda context through Mahāyāna scholastic frames, modern psychology, MBSR, or self-help language.
- Mahāyāna-region general Buddhist terms are not banned as words; banned is imposing a Mahāyāna interpretive framework on the source.
- Put interpretive additions into `grammar_notes` or `doctrinal_notes`.
- If unsure, record uncertainty rather than guessing.
- Do not write in sermon style.
- Quality is judged by accuracy, restraint, and consistency, not length.

`literal_ko` policy:

- For reviewers and researchers.
- Prefer strict Korean terms aligned with the Early Buddhist Texts Translation Institute style.
- Preserve Pāli sentence structure, word order, predicates, case relations, and causal/conditional relations.
- Korean may be slightly awkward.
- Do not force missing subjects or objects into the sentence.
- Do not add explanation, paraphrase, modern psychological interpretation, or Mahāyāna reinterpretation.

`natural_ko` policy:

- For readers.
- Use Early Buddhist Texts Translation Institute terminology and interpretation as the baseline.
- If needed for comprehension, use general Buddhist terms or common Korean expressions with restraint.
- Do not mix explanation into the translation body.
- Keep source meaning conservative.
- Move necessary explanation to `grammar_notes` or `doctrinal_notes`.
- Avoid excessive polishing, emotive style, sermon style, and self-help phrasing.

Terms policy:

- `terms` is a glossary seed.
- Record only key Pāli terms.
- Maximum 5 items.
- Use `[]` if no key term is needed.
- Each item contains `pali`, `ko`, `gloss`, and `note`.
- `ko` should use the standard strict term when possible.
- If `natural_ko` uses a reader-friendly expression, still record the standard term in `terms`.
- `note` is at most one sentence explaining the local choice.
- Do not include ordinary conjunctions, particles, or semantically weak words.

Grammar notes policy:

- Maximum 3 items.
- Use only when grammar needs explanation.
- Keep each item short.
- Use for compounds, sandhi, case relations, relative clauses, ellipsis, or ambiguous grammar.
- Simple passages should use `[]`.

Doctrinal notes policy:

- Maximum 3 items.
- Each item is at most 1-2 sentences.
- Use only for doctrinal background that cannot belong in the translation body.
- Stay grounded in early Buddhist / Theravāda context.
- Briefly note important commentarial meaning where relevant.
- Do not write sermons, reflections, modern psychology, or self-help advice.
- If uncertain, use `uncertainties` instead.

Uncertainties policy:

- Maximum 3 items.
- Use for uncertain grammar, ambiguous terms, context gaps, or source-state issues.
- Use `[]` if no uncertainty exists.
- Be honest about uncertainty.
- Do not present guesses as settled interpretation.
- Do not hide uncertainty by smoothing `natural_ko`.

Model self-reported `quality_flags` policy:

- These are model self-report flags only.
- Use `[]` if there is no issue.
- Allowed values:
  - `grammar_uncertain`
  - `doctrinal_risk`
  - `low_confidence`
  - `possible_glossary_conflict`
  - `needs_human_review`
- The model must not emit local-validator flags.
- Local-validator flags include `json_parse_failed`, `schema_validation_failed`, `empty_translation`, `too_short`, `too_long`, and `contains_untranslated_pali`.

Core terminology policy:

| Pāli | Korean policy |
| --- | --- |
| `sati` | `마음챙김` |
| `viññāṇa` | `알음알이` |
| `paññā` | `통찰지` |
| `āyatana` / `saḷāyatana` | `(여섯) 감각장소` |
| `phassa` | `감각접촉` |
| `nibbidā` | `염오` |
| `virāga` | `탐욕의 빛바램` |

Contextual term policy:

- `saṅkhāra` in five-aggregate context: `심리현상들`.
- `saṅkhāra` in dependent-origination context: `의도적 행위들`.
- `saṅkhāra` as conditioned formations / sabbe saṅkhārā aniccā context: `형성된 것들`.
- For `anussati` and memory/recollection contexts, do not mechanically translate `sati` only as `마음챙김`; inspect the context.
- `paññā` remains `통찰지` in `literal_ko` and `terms`; `natural_ko` may use `지혜` only when it improves readability without importing prajñā/emptiness meanings.
- `viññāṇa` remains `알음알이` in `literal_ko` and `terms`; `natural_ko` may use consciousness-like wording only for readability and must not import Yogācāra meaning.
- `nibbāna` may be `열반` in `natural_ko`, but must not be colored as Buddha-nature, tathatā, or original-face discourse.

Output length control:

- `literal_ko` should be concise and proportional to source length.
- `natural_ko` should also avoid unnecessary expansion.
- `terms`: maximum 5.
- `grammar_notes`: maximum 3.
- `doctrinal_notes`: maximum 3.
- `uncertainties`: maximum 3.
- Each note is at most 1-2 sentences.
- Simple passages can have empty note arrays.

Prohibitions:

- No text outside JSON.
- No Markdown code fence.
- No schema-extra fields.
- No English translation field.
- No explanation inserted into `literal_ko` or `natural_ko`.
- No modern psychology / MBSR reinterpretation.
- No Mahāyāna doctrinal reinterpretation of early Buddhist / Theravāda context.
- No self-help phrasing.
- No sermon style or emotive prose.
- No presenting uncertain interpretation as certain.
- No model-generated local-validator flags.
- No excessive `terms` generation.

Schema validation policy:

- `KoreanAdvancedTranslation` rejects extra fields.
- `literal_ko` and `natural_ko` must be non-empty strings.
- `terms`, `grammar_notes`, `doctrinal_notes`, and `uncertainties` enforce the Prompt v1 max lengths.
- `validate_korean_advanced_model_output()` additionally rejects model output that uses local-validator quality flags.
- Extra fields are treated as schema validation failures, not silently accepted.
- Empty arrays are valid when the field has no useful content.

Smoke batch planner connection:

- `plan_gemini_smoke_batch.py` uses Prompt v1 by default.
- `--prompt-version korean_advanced_v1_schemafix` is the current supported prompt option.
- The sidecar manifest records `prompt_template_id` and `prompt_template_version`.
- Provider JSONL contains the rendered Prompt v1 text.
- If Prompt v1 changes, regenerate the smoke JSONL and manifest.

Token estimate note:

- Prompt v1 is longer than the previous placeholder prompt.
- The old placeholder overhead (`106` tokens) is deprecated and must not be used for Prompt v1 planning.
- Prompt v1 overhead has been remeasured with Gemini `countTokens`; use the Prompt v1 artifact for smoke and pilot input-token estimates.
- This stage still does not call `generateContent`, GPT, or Batch submit.

## 6. Quality Flags and Arbitration Policy

Quality flags:

- `json_parse_failed`
- `schema_validation_failed`
- `empty_translation`
- `too_short`
- `too_long`
- `contains_untranslated_pali`
- `glossary_conflict`
- `possible_glossary_conflict`
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
| `possible_glossary_conflict` | `model_self_report` |
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

### Gemini Batch Billing Path Verification

The 75-segment pilot batch `batches/w1h2mcfla5uymac1pauiveazrq5e9dw3ngum` was submitted by
`backend/pali/scripts/submit_gemini_smoke_batch.py`, not by the RAG runtime path.

Credential resolution for this submitter is API-key only:

1. Process environment:
   - `GEMINI_API_KEY`
   - `GOOGLE_API_KEY`
   - `GOOGLE_GENAI_API_KEY`
   - `PALI_GEMINI_API_KEY`
2. Local repo `.env`
3. Local `config/.env`

Because the submitter calls `resolve_gemini_api_key()` and then constructs `GeminiBatchRestClient(api_key=...)`,
the Batch API path is the Gemini Developer API / AI Studio API-key path. The request URL is:

```text
https://generativelanguage.googleapis.com/v1beta/{model}:batchGenerateContent?key=<api-key>
```

The submitter does not initialize Vertex AI, does not pass `vertexai=True`, and does not use
`GOOGLE_APPLICATION_CREDENTIALS`, ADC, or a GCP service account for Batch submission. Existing Buddha Korea RAG
traffic may still use Vertex AI, but this pilot batch did not use that code path.

For the local environment used by this workflow, `.env` and `config/.env` contain non-empty `GEMINI_API_KEY` and
`PALI_GEMINI_API_KEY` entries. Since `GEMINI_API_KEY` is first in the resolver order and the command did not pass an
explicit `--api-key`, the code-level attribution is: root `.env` `GEMINI_API_KEY` was the first eligible credential.
The key value must never be printed, logged, committed, or stored in artifacts.

Verified credential note:

- The API key fingerprint used by the local resolver was `6c570f7ed099`.
- The same key was found in the Google AI Studio API key list for the BuddhaKorea project
  `gen-lang-client-0324154376` by matching the visible key suffix in the dashboard.
- Therefore a project/key mismatch is currently unlikely for this pilot Batch path.
- The fingerprint is a local SHA-256 prefix used only for safe operator comparison. It is not a Google-provided key id
  and must not be treated as a secret-bearing artifact.

Code-level limitations:

- The returned Batch ID is only `batches/...`; it does not encode a visible Google Cloud project or API-key owner.
- The local artifacts store provider batch id, model, usage metadata, and local estimated/actual cost fields, but not
  the API key identity.
- Therefore the exact Google billing account/project must be confirmed in Google dashboards, not inferred from the
  artifact alone.

Cost fields in Pali artifacts:

- `price_profile_source_url` points to the public pricing page used by the local estimator.
- `total_actual_cost_usd` is a local calculation from provider usage metadata and the injected price profile.
- It is not a Google invoice, not an authoritative billing export, and not proof of actual charged spend.

Actual spend verification paths:

- AI Studio Dashboard > Usage.
- AI Studio Billing/Spend > Prepay credits.
- Google Cloud Billing Reports > Group by Service > Gemini API.
- Cloud Billing Reports > Group by SKU with Services filter set to Gemini API.
- Billing graphs and SKU-level costs can lag by up to 24 hours, so recent Batch usage may not appear immediately.

Current dashboard reconciliation status:

- AI Studio Usage shows requests for the Batch activity.
- Google Cloud Billing Reports did not yet show Gemini API cost for June 10-13 at the time of verification.
- The June 2 KRW 50 charge appears to be Vertex AI cost and should be treated as separate from this Gemini Developer
  API Batch pilot.
- Production work must not proceed on local estimator values alone. Before any production-scale Batch run, confirm
  AI Studio spend caps/prepay credit behavior and verify that Gemini API charges appear in the expected billing view.

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

Deprecated: the placeholder overhead above was useful only before Prompt v1 existed. It must not be used for smoke, pilot, or production planning after `korean_advanced_v1_schemafix`.

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

### 7.1 Prompt v1 Schemafix countTokens recalibration

Prompt overhead is measured separately because the finalized Korean Advanced prompt is much longer than the earlier placeholder wrapper. After the schemafix prompt update, `korean_advanced_v1_schemafix` is the current pilot-candidate prompt version.

Command:

```bash
./venv/bin/python backend/pali/scripts/calibrate_prompt_v1_tokens.py \
  --samples data/reports/pali/vri_translation_sample_candidates_49bc869.json \
  --sample-set calibration_samples \
  --model models/gemini-3.1-pro-preview \
  --out data/reports/pali/gemini_prompt_v1_schemafix_token_calibration_49bc869.json \
  --max-samples 150 \
  --timeout-seconds 60 \
  --max-retries 2 \
  --retry-backoff-seconds 2 \
  --pretty
```

Result for source commit `49bc86914748589a2501b548cc6b3e97a8abe018`:

- Prompt template: `korean_advanced` / `korean_advanced_v1_schemafix`.
- Model: `models/gemini-3.1-pro-preview`.
- Sample size: 150.
- Successful samples: 150.
- Failed samples: 0.
- Source text only total: 30,337 tokens.
- Prompt with source total: 422,768 tokens.
- Prompt overhead total: 392,431 tokens.
- Average Prompt overhead: 2,616.206667 tokens.
- Median Prompt overhead: 2,617 tokens.
- P90 Prompt overhead: 2,627 tokens.

Schemafix overhead by text layer:

| text_layer | samples | source text only | prompt with source | overhead total | avg overhead | median | p90 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `mula` | 50 | 9,801 | 140,378 | 130,577 | 2,611.54 | 2,613.5 | 2,619 |
| `atthakatha` | 50 | 10,361 | 141,304 | 130,943 | 2,618.86 | 2,621 | 2,629 |
| `tika` | 50 | 10,175 | 141,086 | 130,911 | 2,618.22 | 2,618 | 2,627 |

Schemafix overhead by chunk type:

| chunk_type | samples | source text only | prompt with source | overhead total | avg overhead | median | p90 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `prose` | 88 | 24,658 | 254,881 | 230,223 | 2,616.170455 | 2,616 | 2,626 |
| `verse` | 62 | 5,679 | 167,887 | 162,208 | 2,616.258065 | 2,617.5 | 2,629 |

Comparison with pre-schemafix `korean_advanced_v1`:

- Average overhead: 1,845.206667 -> 2,616.206667.
- Median overhead: 1,846 -> 2,617.
- P90 overhead: 1,856 -> 2,627.
- Total prompt overhead on the 150-sample calibration set: 276,781 -> 392,431.
- Prompt overhead increase ratio: 1.417839.
- 75-sample pilot estimated input tokens: 147,676 -> 205,501.
- Full corpus approximate input tokens: 404,538,379 -> 561,509,353.
- Full corpus estimate method: corrected source tokens plus layer-average prompt overhead per segment. This is a planning estimate, not a final production cost.

Prompt v1 input-token estimate policy:

- Use official `source_text_only_tokens` from source correction for source scale.
- Add Prompt v1 schemafix overhead from `gemini_prompt_v1_schemafix_token_calibration_<commit>.json`.
- For smoke planning, prefer text-layer average Prompt v1 overhead when available; fall back to overall average only when no layer-specific value exists.
- Do not use the deprecated placeholder overhead of `106`.
- Output and thinking token estimates for pilot planning are rough ratios from the 5-segment schemafix smoke. They are not final production estimates.
- Official price-based cost calculation remains out of scope until current price profiles are injected explicitly.

75-sample pilot estimate artifact:

```bash
./venv/bin/python backend/pali/scripts/estimate_gemini_pilot_batch.py \
  --samples data/reports/pali/vri_translation_sample_candidates_49bc869.json \
  --source-calibration data/reports/pali/gemini_token_calibration_49bc869.json \
  --previous-prompt-calibration data/reports/pali/gemini_prompt_v1_token_calibration_49bc869.json \
  --schemafix-prompt-calibration data/reports/pali/gemini_prompt_v1_schemafix_token_calibration_49bc869.json \
  --smoke-summary data/reports/pali/gemini_smoke_batch_49bc869_prompt_v1_schemafix_summary.json \
  --corpus-corrected-summary data/reports/pali/vri_romn_corpus_token_summary_gemini_corrected_49bc869.json \
  --out data/reports/pali/gemini_pilot_75_prompt_v1_schemafix_estimate_49bc869.json \
  --model models/gemini-3.1-pro-preview \
  --pilot-size 75 \
  --budget-cap-usd 50 \
  --price-profile config/pali_batch_price_profiles.example.json \
  --price-profile-id official_gemini_3_1_pro_preview_batch_2026_06_13 \
  --pretty
```

Pilot estimate result:

- request_count: 75.
- estimated_input_tokens: 205,501.
- estimated_output_tokens: 25,859.
- estimated_thinking_tokens: 66,599.
- estimated_cost_usd: 0.760249.
- budget cap: 50 USD.
- budget check: pass.

Pilot preconditions:

- Use prompt version `korean_advanced_v1_schemafix`.
- Use model `models/gemini-3.1-pro-preview`.
- Use `gemini_prompt_v1_schemafix_token_calibration_49bc869.json` for prompt overhead.
- Use a hard pilot cap and preflight validation before submit.
- Do not submit the 75-sample pilot without explicit human approval.
- After the pilot, manually review translation quality before any larger batch.

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

## 10. Gemini Batch API Translation Flow

This section is a design only. It does not submit Gemini Batch jobs and does not call `generateContent`.

Official Gemini Batch API notes to preserve in implementation:

- Batch API is asynchronous and intended for large, non-urgent workloads.
- Batch requests can be submitted inline or through an uploaded JSONL file.
- For larger jobs, JSONL input is preferred.
- Each JSONL line contains a user-defined `key` and a `request` object.
- The output JSONL line can be a `GenerateContentResponse` or a status/error object.
- Batch jobs return a provider job name that must be used for polling and result retrieval.

Confirmed model:

- Default high-quality translation model target: `models/gemini-3.1-pro-preview`.
- Do not fall back to Flash-family models for canonical translation.

### 10.1 Batch Job Lifecycle

Planned lifecycle:

1. Create a local translation job record.
2. Expand the selected source scope into canonical segment items.
3. Estimate source input tokens from the corrected Gemini source token report.
4. Estimate output tokens using a pilot-derived output multiplier. This is not available yet.
5. Split items into bounded batch shards.
6. Create provider JSONL per shard.
7. Create local sidecar metadata per shard keyed by `stable_segment_key`.
8. Run preflight budget check.
9. Reserve estimated budget for the shard.
10. Upload JSONL through the Files API.
11. Submit Gemini Batch job.
12. Store provider batch id/name.
13. Poll status.
14. On completion, download result JSONL.
15. Map each result line back by `key` / `stable_segment_key`.
16. Parse successful response text as Korean Advanced JSON.
17. Extract `usage_metadata`.
18. Reconcile estimated vs actual token usage and cost.
19. Mark failed or missing-usage items as `needs_retry`.
20. Creating `translation_versions` is a later implementation phase.

Terminal provider states should be treated as final for the shard:

- `JOB_STATE_SUCCEEDED`
- `JOB_STATE_FAILED`
- `JOB_STATE_CANCELLED`
- `JOB_STATE_EXPIRED`

### 10.2 JSONL Request Format

Provider JSONL should stay close to the official Batch API shape:

```json
{
  "key": "stable_segment_key",
  "request": {
    "contents": [
      {
        "role": "user",
        "parts": [
          {
            "text": "..."
          }
        ]
      }
    ],
    "generation_config": {
      "temperature": 0.2,
      "response_mime_type": "application/json"
    }
  }
}
```

Local sidecar metadata should not be relied on as provider-accepted JSONL fields unless verified against the current SDK/API. Keep a separate manifest keyed by the same `stable_segment_key`:

```json
{
  "stable_segment_key": "...",
  "source_text_hash": "...",
  "source_path": "...",
  "text_layer": "...",
  "chunk_type": "...",
  "estimated_input_tokens": 0,
  "estimated_output_tokens": 0,
  "estimated_thinking_tokens": 0,
  "estimated_cost_usd": "0.000000"
}
```

Mapping rule:

- Provider request `key` must be exactly `stable_segment_key`.
- Sidecar manifest must also use `stable_segment_key`.
- Result parser must reject duplicate keys within one shard.
- Result parser must not rely on result ordering.

### 10.3 Result JSONL Parsing

Each output line must be classified independently:

- `succeeded`: line has a response, response text is present, usage metadata is present, and Korean Advanced JSON parse succeeds.
- `needs_retry`: response exists but usage metadata is missing, output JSON parse fails, schema validation fails, or transient provider status is recoverable.
- `failed`: line-level error/status object indicates non-retryable failure.

The provider output may be a normal `GenerateContentResponse` or an error/status object. The parser must preserve raw result payload for audit/debugging, but avoid storing credentials or request secrets.

### 10.4 usage_metadata Collection

Extract from `GenerateContentResponse.usage_metadata` or `usageMetadata`.

Logical fields:

- `prompt_token_count`
- `candidates_token_count`
- `thoughts_token_count`
- `cached_content_token_count`
- `total_token_count`

Policy:

- `prompt_token_count` is actual input tokens.
- `candidates_token_count` is actual output tokens.
- `thoughts_token_count`, if present, is recorded separately and included in actual cost calculations when the injected price profile defines a thinking-token price.
- `cached_content_token_count`, if present, is stored for caching analysis.
- `total_token_count` is stored as provider-reported total.
- Missing usage metadata means the item is `needs_retry` or `failed`; it cannot be reconciled as successful.

### 10.5 Estimated vs Actual Token Accounting

Preflight estimated fields:

- `estimated_input_tokens`
- `estimated_output_tokens`
- `estimated_thinking_tokens`
- `estimated_cost_usd`

Actual fields after result parse:

- `actual_input_tokens`
- `actual_output_tokens`
- `actual_thinking_tokens`
- `actual_cached_content_tokens`
- `actual_total_tokens`
- `actual_cost_usd`

Corrected source token estimate:

- Use corrected Gemini source token report for source text.
- Add prompt overhead only after Korean Advanced Prompt v1 is finalized.
- Estimate output tokens from pilot translation output multiplier later.

### 10.6 Batch Cost Estimation and Budget Reservation

Prices must not be hardcoded. Inject a price profile:

```json
{
  "input_usd_per_million_tokens": "CONFIGURED_AT_RUNTIME",
  "output_usd_per_million_tokens": "CONFIGURED_AT_RUNTIME",
  "thinking_usd_per_million_tokens": "CONFIGURED_AT_RUNTIME",
  "batch_discount_multiplier": "CONFIGURED_AT_RUNTIME"
}
```

Submission guard:

```text
actual_spent_usd
+ reserved_open_batches_usd
+ new_batch_estimated_cost_usd
<= hard_cap_usd
```

Default planning caps:

- Production hard cap example: `3000 USD`.
- First smoke batch cap: `5 USD`.
- Pilot batch cap: `20-50 USD`.

Reservation model:

1. Estimate shard cost.
2. Check hard cap.
3. If allowed, add estimate to `reserved_open_batches_usd`.
4. Submit batch.
5. On completion, calculate actual cost from usage metadata.
6. Subtract reserved estimate.
7. Add actual cost to `actual_spent_usd`.
8. If actual cost exceeds estimate, the delta reduces remaining hard-cap budget.

### 10.7 Hard Cap, Kill Switch, and Cancellation

Hard cap policy:

- If projected total exceeds hard cap, do not submit a new batch.
- Include open reservations in all checks.
- Never assume pending/running batches can stop exactly at a target dollar amount.

Kill switch policy:

- If operator kill switch is enabled, do not submit new batches.
- Attempt to cancel pending/running provider batches.
- Mark local batches as `cancellation_requested`.
- Continue polling until provider returns terminal state.
- Reconcile any partial results and actual usage reported by the provider.

Cancellation policy:

- Cancellation may not prevent already processed requests from being billed.
- Loss boundary is controlled by shard size, not by mid-shard cancellation.
- Production shards must be small enough that one shard failure or late cancellation is financially bounded.

### 10.8 Batch Shard Policy

Never submit the full corpus as one batch.

Initial pilot policy:

- First smoke batch: `3-5` segments or estimated cost `<= 5 USD`.
- Pilot batch: existing `75` sample segments or estimated cost `<= 20-50 USD`.

Production planning policy:

- one shard estimated cost `<= 100 USD`;
- one shard `<= 5000` segments;
- JSONL file size well below provider limit;
- first production run must be one literature or one literature subset, not the full corpus.

The shard limits are safety controls. Reduce shard size if provider latency, cancellation behavior, parse failure rate, or actual/estimated cost drift is worse than expected.

### 10.9 Retry Policy and Failure Modes

Retryable item-level failures:

- transient provider errors;
- missing usage metadata;
- malformed JSON output;
- schema validation failure;
- timeout while fetching result line;
- recoverable safety block if policy allows prompt adjustment.

Non-retryable or operator-review failures:

- source segment missing or hash mismatch;
- stable key collision;
- repeated JSON/schema failure after retry limit;
- provider model unavailable;
- account/billing/permission failure;
- budget hard cap violation;
- kill switch enabled.

Model-level errors such as `404 model not found` or unsupported `countTokens`/Batch capability must fail before shard submission. They are not per-segment retry targets.

### 10.10 Context Caching Position

Context caching is not the MVP cost-control mechanism.

Position:

- First reduction mechanism: Batch API.
- Second reduction mechanism: compact prompt design.
- Future optimization: explicit context caching.

Why not MVP:

- Short segment-level prompts may have limited cache hit value.
- Cache setup adds lifecycle and invalidation complexity.
- Large shared glossary, DPD context, or document-level context is not finalized yet.
- Batch requests may reference cached content in future, but MVP avoids this complexity.

Revisit caching when:

- Korean Advanced Prompt v1 is stable;
- glossary/context blocks become large and repeated;
- literature-level context is shared across many segments;
- usage metadata shows prompt overhead dominates.

### 10.11 Logical Cost Fields

No DB migration is created in this phase.

`translation_jobs` candidate fields:

- `budget_limit_usd`
- `estimated_cost_usd`
- `reserved_cost_usd`
- `actual_cost_usd`
- `budget_status`
- `kill_switch_enabled`

`translation_batches` candidate fields:

- `id`
- `job_id`
- `provider_batch_id`
- `model`
- `status`
- `request_count`
- `estimated_input_tokens`
- `estimated_output_tokens`
- `estimated_cost_usd`
- `reserved_cost_usd`
- `actual_input_tokens`
- `actual_output_tokens`
- `actual_thinking_tokens`
- `actual_total_tokens`
- `actual_cost_usd`
- `submitted_at`
- `completed_at`
- `cancelled_at`
- `result_file_name`
- `error_message`

`translation_job_items` candidate fields:

- `stable_segment_key`
- `batch_id`
- `estimated_input_tokens`
- `estimated_output_tokens`
- `actual_input_tokens`
- `actual_output_tokens`
- `actual_thinking_tokens`
- `actual_total_tokens`
- `estimated_cost_usd`
- `actual_cost_usd`
- `status`

Implemented local-only helper skeletons:

- `backend/pali/translation/budget.py`
- `backend/pali/translation/batch_plan.py`

These helpers are pure functions/dataclasses only. They do not call providers, connect to DB, or store official prices.

### 10.12 Smoke Batch Dry-Run Planner

Implemented local planner:

- `backend/pali/scripts/plan_gemini_smoke_batch.py`

Purpose:

- Generate provider JSONL just before the point where a Gemini Batch job would be submitted.
- Generate a separate local sidecar manifest.
- Validate stable-key mapping before any real provider call.
- Run budget guardrail checks locally.
- Keep the first smoke batch to 3-5 segments.

Example:

```bash
./venv/bin/python backend/pali/scripts/plan_gemini_smoke_batch.py \
  --samples data/reports/pali/vri_translation_sample_candidates_49bc869.json \
  --model models/gemini-3.1-pro-preview \
  --out-jsonl data/reports/pali/gemini_smoke_batch_49bc869_prompt_v1_schemafix.jsonl \
  --out-manifest data/reports/pali/gemini_smoke_batch_49bc869_prompt_v1_schemafix_manifest.json \
  --max-segments 5 \
  --max-estimated-cost-usd 5 \
  --prompt-version korean_advanced_v1_schemafix \
  --prompt-token-calibration data/reports/pali/gemini_prompt_v1_token_calibration_49bc869.json \
  --pretty-manifest
```

Provider JSONL artifact:

```text
data/reports/pali/gemini_smoke_batch_49bc869_prompt_v1_schemafix.jsonl
```

Sidecar manifest artifact:

```text
data/reports/pali/gemini_smoke_batch_49bc869_prompt_v1_schemafix_manifest.json
```

Provider JSONL rules:

- one JSON object per line;
- each line has `key` equal to `stable_segment_key`;
- each line has a Gemini `request` body;
- internal-only metadata is not placed in provider JSONL;
- no API key or credential values are stored.

Sidecar manifest rules:

- stores source identity and estimated token/cost details;
- maps `jsonl_line_index` to `stable_segment_key`;
- records `source_text_hash`, `source_path`, `text_layer`, `pitaka`, `nikaya`, `chunk_type`, and `length_bucket`;
- records budget check result;
- records validation result.

Smoke planner validation:

- JSONL line count equals manifest item count;
- all keys are unique;
- provider JSONL key order matches manifest `stable_segment_key` order;
- every manifest item has `source_text_hash`;
- `jsonl_line_index` is exact;
- provider JSONL lines are valid JSON;
- request contents include source text block;
- estimated cost is within `max_estimated_cost_usd`;
- manifest does not contain credential-like markers.

Prompt policy:

- The planner uses `korean_advanced` / `korean_advanced_v1_schemafix`.
- The generated JSONL must be regenerated whenever Prompt v1 changes.
- Prompt v1 overhead is read from `gemini_prompt_v1_token_calibration_<commit>.json` when available.
- The deprecated placeholder overhead of `106` tokens must not be used for Prompt v1 planning.
- Smoke batch is for request shape, sidecar mapping, and budget guardrail verification, not translation quality evaluation.

Price profile:

- Default local profile: `config/pali_batch_price_profiles.example.json`.
- This file contains mock planning values only.
- Replace with current official pricing before any real submission.
- Official prices must be configuration input, not hardcoded in Python.

Current Prompt v1 dry-run artifact summary for source commit `49bc86914748589a2501b548cc6b3e97a8abe018`:

- request count: 5;
- prompt id/version: `korean_advanced` / `korean_advanced_v1_schemafix`;
- prompt token calibration: `data/reports/pali/gemini_prompt_v1_token_calibration_49bc869.json`;
- provider JSONL: `data/reports/pali/gemini_smoke_batch_49bc869_prompt_v1.jsonl`;
- sidecar manifest: `data/reports/pali/gemini_smoke_batch_49bc869_prompt_v1_manifest.json`;
- estimated input tokens: 9,328;
- estimated output tokens: 27,984;
- estimated cost with mock profile: `0.326480 USD`;
- budget cap: `5 USD`;
- budget result: `ok`;
- validation result: `valid`;
- layer distribution: `mula=1`, `atthakatha=3`, `tika=1`;
- chunk distribution: `prose=3`, `verse=2`;
- length distribution: `short=4`, `medium=1`.
- note: these token/cost estimates use calibrated source-token correction, Prompt v1 countTokens overhead, and a mock output-token multiplier. They still do not know actual output tokens because no translation generation has been run.

Next phase after this planner:

- only after explicit approval, submit a 3-5 segment smoke Batch job;
- reconcile the smoke result's actual `usage_metadata` against this estimate.

## 11. Cost Analysis Boundary

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

## 12. Implementation Roadmap

1. Keep improving VRI XML canonical segment identity and validation.
2. Add prompt template versioning for `korean_advanced`.
3. Add sample selector for calibration and pilot runs.
4. Run Gemini countTokens sample calibration.
5. Design Batch API shard planning and budget guardrails.
6. Run first smoke batch with 3-5 segments only after explicit approval.
7. Run 50-100 segment pilot with Gemini 3.1 Pro.
8. Validate output schema and quality flags.
9. Run GPT-5.5 arbitration on flagged pilot subset.
10. Decide publication policy for machine drafts.
11. Only then design DB migrations for jobs, job items, and translation versions.
12. Only after calibration and pilot, perform official price-based cost analysis.

## 13. Out of Scope

- Actual LLM API calls.
- Bulk translation execution.
- DB migration creation.
- RAG.
- Embedding.
- Official price-based cost calculation.
- Modifying existing `translate.py` or `gemini_client.py`.
- Making Gemini Flash-family models the default high-quality translator.
