# Pali Translation QA Infrastructure v1.1

## 1. Purpose

QA Infrastructure v1.1 extends the deterministic glossary layer without changing the active translation prompt. The baseline prompt remains `korean_advanced_v1_schemafix_qa_patch_v2`.

This layer does not generate translations. It reads parsed translation artifacts and existing local validator flags, then produces more precise QA signals for review.

The v1.1 scope is:

- cross-term collision review signals
- avoid-term conflict checks with source co-occurrence gating
- read-only reclassification of `contains_untranslated_pali`
- citation display mapping, including composite citations

## 2. Cross-Term Collision Philosophy

Glossary consistency for a single headword is not enough. A model can keep each Pāli headword individually consistent while collapsing two different Pāli terms into the same Korean rendering.

Example:

- `dhīra -> 현자`
- `paṇḍita -> 현자`

This is a cross-term collision. It does not automatically mean the translation is wrong, but it should be reviewed because the source distinction may have disappeared.

## 3. Declared Cross-Avoid Pairs Only

v1.1 never compares all Pāli term pairs. All-pairs comparison would create too many false positives.

Cross-term collision checks only pairs explicitly declared in `data/controlled_glossary.json` via `cross_avoid`.

Initial active pair:

- `dhīra <-> paṇḍita`

Existing botanical distinction pairs such as `uppala <-> paduma` can also be represented through declared `cross_avoid`, but they are still checked only when both terms are present in the same segment evidence.

Future candidates, not implemented in v1.1:

- `paññā <-> ñāṇa`
- `citta <-> viññāṇa`
- `saññā <-> paññatti`

The hard signal is same-segment collision. Batch/global repeated sharing is only diagnostic in v1.1.

## 4. Avoid-KO Co-Occurrence Gating

`avoid_ko` checks must be gated by source evidence. A Korean string is not a violation unless the corresponding Pāli source term is detected by exact/stem matching.

Example:

- source has `uppala`
- translation has `연꽃`
- report an `avoid_ko` conflict candidate

Counterexample:

- source has only `paduma`
- translation has `연꽃`
- do not report an `uppala` conflict

The matcher reuses the exact/stem glossary matcher from `backend/pali/translation/glossary.py`. Substring matching is not used.

Known limitation: if source contains both `uppala` and `paduma`, simple co-occurrence gating cannot know which Pāli term produced the Korean word. v1.1 accepts this limitation and avoids hard judgment in such ambiguous co-occurrence cases.

## 5. Contains-Untranslated-Pali Reclassification

The existing local validator flag is not changed. v1.1 reads `contains_untranslated_pali` and reclassifies the detected roman/Pāli-like strings.

Categories:

- `allowed_parenthetical_pali`
- `allowed_bracketed_pali`
- `allowed_text_title`
- `allowed_person_name`
- `allowed_citation_abbreviation`
- `allowed_technical_term`
- `possible_true_untranslated_pali`
- `unknown`

Allowed examples include parenthetical source terms, bracketed technical terms, known text titles, known person names, and citation abbreviations. This reclassification must not hide true untranslated Pāli in the main Korean flow.

Positive control: a sentence containing `anicca dukkha anattā` in the main body remains `possible_true_untranslated_pali`.

## 6. Citation Mapping

Raw citation text is preserved. The deterministic layer creates display labels only.

Examples:

- `saṃ. ni.` -> `상윳따 니까야`
- `dī. ni.` -> `디가 니까야`
- `ma. ni.` -> `맛지마 니까야`
- `aṅ. ni.` -> `앙굿따라 니까야`
- `jā.` -> `자따까`
- `visuddhi.` -> `청정도론`

LLMs should not be asked to translate citation abbreviations ad hoc. Citation display should come from a table.

## 7. Composite Citation Handling

Many citations are composite:

- `dī. ni. aṭṭha. 2.95`
- `sārattha. ṭī. 1.1`
- `paṭi. ma. aṭṭha.`

v1.1 decomposes these into:

1. base text abbreviation
2. layer suffix
3. numeric locator

Layer suffix examples:

- `aṭṭha.` -> `주석`
- `ṭī.` -> `복주석`

Display examples:

- `dī. ni. aṭṭha. 2.95` -> `디가 니까야 주석 2.95`
- `sārattha. ṭī. 1.1` -> `사라앗타 복주석 1.1`
- `paṭi. ma. aṭṭha.` -> `빠띠삼비다막가 주석`

## 8. Positive-Control Testing

Tests must include positive controls so the whitelist does not hide real errors.

Required examples:

- declared `cross_avoid` only; no all-pairs collisions
- `dhīra` and `paṇḍita` with the same Korean rendering in the same segment produce `cross_term_collision_review`
- source without `uppala` must not trigger `uppala` `avoid_ko`
- source with `uppala` and `연꽃` should trigger an avoid conflict candidate
- parenthetical Pāli is reclassified as allowed
- main-flow `anicca dukkha anattā` remains possible true untranslated Pāli
- composite citation display mapping preserves the raw citation

## 9. Known Limitations

v1.1 is intentionally conservative.

- It does not validate whether a `context_variant` rendering is correct for that exact context.
- If `saṅkhāra` is translated with one of its allowed variants, v1.1 does not decide whether that variant is doctrinally correct in the segment.
- If source contains both sides of a cross pair, avoid-term attribution may remain ambiguous.
- If the model omits a glossary head term from `terms[]`, cross-term collision detection may miss body-only collapses.
- Citation mapping covers common abbreviations and composites, not the entire VRI/PTS abbreviation universe.

## 10. Out Of Scope

The following remain out of scope:

- prompt changes
- Gemini Batch submission
- `generateContent` or any LLM call
- GPT calls
- DB migrations
- DB writes
- RAG or embeddings
- production translation
- large glossary expansion
- context-aware semantic validation
- admin UI
