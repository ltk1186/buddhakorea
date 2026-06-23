# Pāli natural_ko Calibration

## Purpose

Step 5.5 is inserted after the pilot_1000 selection and before Step 6 because the 300-pilot `natural_ko` output often reads too close to `literal_ko`. The issue is not the output schema. The issue is that `natural_ko` must more clearly fulfill its intended role.

No Gemini, LLM, Batch, or network calls are made in Step 5.5-A/B. This step parses existing 300-pilot readable outputs, audits readability, selects 30 diagnostic calibration samples, drafts an experiment-only `natural_ko_v2` prompt variant, and prepares dry-run request previews.

## Field Semantics

`literal_ko` is a scholarly literal translation that preserves Pāli/source structure for review.

`natural_ko` is a publishable modern Korean Buddhist-book translation. It should preserve doctrinal meaning, referents, and logical relations, but it should not preserve Pāli word order, repetitive lemma-gloss syntax, or overly literal clause structure merely because `literal_ko` does.

`reader_ko` is not being added. The target is to improve `natural_ko` itself.

## Audit Metrics

The audit computes deterministic local metrics:

- literal/natural string similarity
- natural-to-literal length ratio
- sentence count and average sentence length
- Pāli parenthetical and Pāli token carry-over
- lemma quote and formulaic gloss phrase counts
- exact and near-literal flags
- formulaic or matrix-like caveat flags

Total `natural_ko` length is not a success axis. Better Korean re-expression can preserve or increase total length. The readability target is clearer Korean, often through shorter sentences and less lemma-gloss repetition.

## Calibration 30

The calibration set contains 30 existing 300-pilot outputs:

- 10 `mula`
- 10 `atthakatha`
- 10 `tika`

Each item is tagged with a calibration role:

- `improvement_target`: narrative, verse, discursive commentary, subcommentary, or lemma-gloss prose that should become more readable.
- `convergence_control`: Abhidhamma matrix, numeric list, very short Q-A, or formulaic passage where forcing divergence would be a failure.

The selection intentionally includes exact literal/natural duplicates and high-similarity offenders. It is diagnostic, not easy.

## Controlled Later Smoke

The later Step 5.5-C/D smoke must isolate the prompt change from the output-method change. Both arms use response_schema:

- A′: current production prompt v1, read-only and unchanged.
- B: experiment-only `natural_ko_v2` prompt variant.

The existing 300 free-form output is a reference view only. It is not the controlled baseline.

Planned later smoke size:

- 30 items × 2 arms = 60 requests
- response_schema on
- salvage cascade fallback on
- hard cost cap recommendation: $4

## Future Checks

Step 5.5-C/D should check:

- `literal_ko` stability: A′↔B literal output should remain approximately identical. Large movement means the `natural_ko` prompt change leaked into literal translation behavior.
- Human/scholar fidelity: B `natural_ko` must be checked against `literal_ko` and original Pāli for dropped, added, or distorted doctrinal content. Automated metrics are supporting signals only.
- Readability by role: improvement targets should become more readable; convergence controls should remain faithful and not be artificially rewritten.

## Non-Mutation Guarantees

Step 5.5-A/B does not modify:

- production prompt files
- production schema files
- Step 5 selection outputs
- translations
- source XML
- glossary files
- gold set files
- existing 300 output files

Step 6 remains blocked until the natural_ko_v2 smoke is reviewed.

