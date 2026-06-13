# Pali Glossary Infrastructure v1

This is an intermediate infrastructure spec for deterministic glossary support in Buddha Korea Pali Studio. It does not change the active translation prompt. The current prompt baseline remains `korean_advanced_v1_schemafix_qa_patch_v2`.

## 1. Glossary Philosophy

Glossary enforcement belongs in a deterministic Translation Quality Layer, not only in prompt prose. The prompt may ask the model to be consistent, but consistency must be measurable, reviewable, and reproducible outside the model.

The glossary is not a simple `pali -> Korean` map. Terms have different policy types:

- `fixed`: a term whose Korean rendering can be mostly fixed.
- `context_variant`: a term whose rendering depends on doctrinal or syntactic context.
- `needs_human`: a term whose policy is not approved yet.

This distinction is mandatory. Terms such as `dhamma`, `saṅkhāra`, `sati`, and `khanti` must not be forced into a single Korean word. A deterministic layer should prevent obvious drift without erasing legitimate contextual variation.

## 2. Glossary Lifecycle

Glossary entries move through a review lifecycle:

- `pending`: observed in pilot results, not yet approved.
- `review`: policy candidate exists, but needs further scholar/admin review.
- `approved`: safe for deterministic assertion and prompt-side injection.

Only approved `fixed` entries may be treated as strong consistency assertions. `context_variant` entries in `review` can be used as weak guidance and metrics. `needs_human` entries are never authoritative; they only mark places where a human decision is required.

## 3. Fixed Term

`fixed` entries represent terms where a controlled rendering is useful and low risk.

Required fields:

- `pali`
- `type: fixed`
- `status`
- `canonical_ko`
- `natural_ko_allowed`
- `avoid_ko`

Metrics:

- If a fixed term has one observed Korean rendering and no `avoid_ko` hit, it is consistent.
- If it has two or more observed Korean renderings, report a fixed-term violation.
- If an `avoid_ko` rendering appears in literal/natural text or in `terms[].ko`, report a violation.

Examples in the seed glossary include `khandha`, `manasikāra`, `uppala`, `paduma`, `dhīra`, and `paṇḍita`.

## 4. Context Variant Term

`context_variant` entries represent terms where multiple translations are valid when the context supports them.

Required fields:

- `pali`
- `type: context_variant`
- `status`
- `variants`

Each variant includes:

- `context_key`
- `allowed_ko`
- optional `note`

Metrics:

- Multiple observed Korean renderings are not violations if all are in the allowed variant set.
- A rendering outside the allowed variant set is reported as `unexpected_variant`.
- The metric must not treat the three `saṅkhāra` renderings as inconsistency when they are allowed by the variant policy.

The initial seed includes `saṅkhāra`, `dhamma`, `sati`, and `khanti`. `dhamma` remains `review` and has low injection priority because forcing it too early would create more errors than it prevents.

## 5. Needs Human Term

`needs_human` entries represent unsettled or risky terms.

Required fields:

- `pali`
- `type: needs_human`
- `status: pending` or `review`
- `candidate_ko`
- `note`

These entries are excluded from consistency pass/fail metrics. The deterministic layer reports only observed candidate distribution and human review markers.

`abbokiṇṇa` is the first seed example. Its candidate renderings are recorded as `끊임없음` and `순전함`, with a note that the following `nirantaraṃ` clause may support `끊임없음`, pending human confirmation.

## 6. Dynamic Glossary Injection

Dynamic injection is a future use of the same glossary infrastructure. It must be segment-scoped and bounded:

1. Analyze the source text.
2. Detect glossary terms with exact matching.
3. Select relevant entries.
4. Prioritize high-risk entries, fixed entries, and human-review markers.
5. Render a small injection block, normally capped at 5 to 10 entries.

The full glossary must never be injected into every prompt. `needs_human` entries must not be presented as authoritative translations. They should be rendered only as review markers with candidate possibilities.

The v1 implementation provides `render_injection_block(entries)` only as a skeleton. It does not call any model and does not modify the active prompt.

## 7. Glossary Assertion Metrics

Glossary assertion is read-only analysis over parsed translation JSON.

Core metrics:

- source term match count
- exact `terms[]` observation count
- observed Korean rendering distribution
- avoid-term hit count
- fixed-term violation count
- context unexpected-variant count
- needs-human candidate distribution

Policy:

- `fixed`: one observed rendering is consistent; multiple renderings or `avoid_ko` hits are violations.
- `context_variant`: multiple renderings are allowed if they are listed in the entry's variants.
- `needs_human`: no consistency verdict, only distribution and review signal.

## 8. Glossary Governance

Glossary changes should be small, reviewed, and traceable.

Governance rules:

- Do not add large harvested term lists directly to the approved glossary.
- Promote terms from pilot observations into `pending` or `review` first.
- Move entries to `approved` only after human review.
- Record avoid terms only when there is clear evidence that the rendering is harmful in the target context.
- Treat disputed entries as `needs_human` rather than inventing a false standard.

The first expansion candidates after v1 are `saññā`, `cetanā`, `citta`, `rūpa`, `jhāna`, and `samādhi`, but they should wait until this infrastructure is stable.

## 9. Future RAG Integration

This glossary is deterministic infrastructure, not RAG. Future RAG may use approved glossary entries as metadata or retrieval filters, but v1 does not use embeddings, vector search, fuzzy matching, or statistical term clustering.

Possible future integration:

- expose approved glossary entries to translation memory
- include glossary policy in source display and QA dashboards
- use glossary status in human review queues
- connect citation/source mapping to glossary governance

RAG should not replace deterministic exact matching for core term assertions.

## 10. Out Of Scope

The following are out of scope for v1:

- prompt changes
- Gemini Batch submission
- `generateContent` or any LLM call
- GPT calls
- DB migrations
- DB writes
- RAG or embeddings
- fuzzy matching
- production translation
- large-scale glossary harvesting
- automatic human-review decisions

Adjacent next steps, not implemented here:

- validator whitelist
- citation and source display mapping
- segment routing and preprocessing
- controlled glossary expansion after infrastructure validation
