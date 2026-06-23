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

## Step 5.5-C/D Controlled Smoke Harness

Step 5.5-C/D adds a guarded live-smoke harness. The default command is preflight only and makes no API calls.

Preflight validates:

- 30 selected items
- 2 arms
- 60 planned provider requests
- `source_text_hash` preserved from selection into request previews
- response_schema present in both arms
- no `reader_ko` field in response schema
- A′ uses production prompt v1 natural_ko guidance unchanged
- B replaces the production natural_ko guidance with the v2 calibration block
- generation_config parity between arms
- estimated cost under the $4 cap

Operator sequence:

```bash
./venv/bin/python -m backend.pali.scripts.run_natural_ko_calibration_smoke \
  --out data/reports/pali/natural_ko_calibration_v1 \
  --preflight \
  --pretty

./venv/bin/python -m backend.pali.scripts.run_natural_ko_calibration_smoke \
  --out data/reports/pali/natural_ko_calibration_v1 \
  --submit \
  --pretty

./venv/bin/python -m backend.pali.scripts.run_natural_ko_calibration_smoke \
  --out data/reports/pali/natural_ko_calibration_v1 \
  --poll \
  --pretty

./venv/bin/python -m backend.pali.scripts.run_natural_ko_calibration_smoke \
  --out data/reports/pali/natural_ko_calibration_v1 \
  --fetch \
  --pretty

./venv/bin/python -m backend.pali.scripts.run_natural_ko_calibration_smoke \
  --out data/reports/pali/natural_ko_calibration_v1 \
  --parse \
  --pretty

./venv/bin/python -m backend.pali.scripts.run_natural_ko_calibration_smoke \
  --out data/reports/pali/natural_ko_calibration_v1 \
  --compare \
  --pretty

./venv/bin/python -m backend.pali.scripts.run_natural_ko_calibration_smoke \
  --out data/reports/pali/natural_ko_calibration_v1 \
  --finalize \
  --pretty
```

Finalization remains conditional. Automatic metrics can prepare a recommendation, but adoption requires operator readability review and Pāli-capable fidelity review.

## v2.1 Guard Patch + Verification

The first natural_ko_v2 controlled smoke showed a real readability gain, but review also found targeted fidelity-risk cases. The important finding was not a broad prompt failure: literal movement can reflect normal generation variance, so it should be interpreted with structural checks rather than raw character similarity alone. The relevant checks are whether literal lemma-gloss structure, parenthetical retention, and source-facing literal behavior remain structurally intact while natural_ko becomes more readable.

Two targeted low-severity issues drive the v2.1 guard:

- `s0513a3.att:8cd09caf90eb`: an unsupported causal insertion risk, such as expanding a bare "therefore" into a reason like "선업이 청정하기 때문에".
- `s0514m.mul:88650af1ca41`: an ambiguous-verb risk around `Assāsayi`, where natural_ko must avoid over-committing or adding narrative embellishment.

natural_ko_v2.1 keeps the v2 readability guidance and adds a narrow fidelity guard:

- the guidance applies only to `natural_ko`;
- `literal_ko` remains a strict scholarly literal translation;
- do not add source-unsupported causal explanations, doctrinal evaluations, interpretive conclusions, or narrative detail;
- keep ambiguous readings conservative and record uncertainty in `uncertainties`;
- paragraph merging is allowed, but overlong Korean sentences should be split.

The C-arm verification reuses the existing A′ baseline and keeps B as reference. It submits only C when the operator explicitly runs `--submit-arm C`; default/preflight remains local-only. C uses the same 30 diagnostic items, response_schema, salvage fallback, and generation_config parity with A′. `reader_ko` is still not added.

Operator sequence for v2.1:

```bash
./venv/bin/python -m backend.pali.scripts.run_natural_ko_calibration_smoke \
  --out data/reports/pali/natural_ko_calibration_v1 \
  --preflight \
  --pretty

./venv/bin/python -m backend.pali.scripts.run_natural_ko_calibration_smoke \
  --out data/reports/pali/natural_ko_calibration_v1 \
  --submit-arm C \
  --pretty

./venv/bin/python -m backend.pali.scripts.run_natural_ko_calibration_smoke \
  --out data/reports/pali/natural_ko_calibration_v1 \
  --poll \
  --pretty

./venv/bin/python -m backend.pali.scripts.run_natural_ko_calibration_smoke \
  --out data/reports/pali/natural_ko_calibration_v1 \
  --fetch \
  --pretty

./venv/bin/python -m backend.pali.scripts.run_natural_ko_calibration_smoke \
  --out data/reports/pali/natural_ko_calibration_v1 \
  --parse \
  --pretty

./venv/bin/python -m backend.pali.scripts.run_natural_ko_calibration_smoke \
  --out data/reports/pali/natural_ko_calibration_v1 \
  --compare-v2-1 \
  --pretty

./venv/bin/python -m backend.pali.scripts.run_natural_ko_calibration_smoke \
  --out data/reports/pali/natural_ko_calibration_v1 \
  --finalize-v2-1 \
  --pretty
```

`--finalize-v2-1` should be run only after operator readability review and Pāli-capable scholar fidelity review. If C preserves the readability gain and fixes the targeted causal/over-commit risks, Step 6 may proceed with `natural_ko_v2_1`. If causal insertion, ambiguous-verb overcommit, or over-paraphrase remains, revise to v2.2 and retest.

## v2.2 D-arm Repair

natural_ko_v2.2 is a D-arm prompt repair for the same 30 diagnostic items. It is not a production prompt mutation and it does not start Step 6.

The D-arm goal is narrower than "make Korean more natural":

- preserve C v2.1's fidelity discipline;
- recover B v2's readability and paragraph-level recomposition;
- preserve A′/baseline literal conservatism where needed;
- avoid B-style unsupported additions;
- avoid C-style omission, double-negation failure, small inserted qualifiers, and literal-regression;
- keep established Korean Buddhist terminology conventions;
- remove awkward square-bracket supplementation such as `[뜻이다]`, `[이다]`, `[마찬가지이다]`, `[설해지지]`, and `[이것을]`.

The D prompt injects only the relevant genre-mode block per item, rather than all genre policies in every request. This is intentional: it reduces over-constraint and avoids pushing the model back into literal-regression.

The D prompt also embeds `glossary_lock_v2_2` in the request. The lock steers the model and the post-hoc objective gate verifies disallowed renderings. High-confidence locks include `sikkhā → 공부지음`, `cāritta → 작지`, `vāritta → 지지`, `paññuttara → 통찰지를 으뜸으로 삼는/최상으로 삼는`, `ādibhāva → 처음이 됨/시작이 됨`, and `accenti → 지나간다/지나쳐 버린다`. Context-sensitive items such as `yama/niyama`, `viññatti`, `otaraṇā`, `appavatti`, and `ājīvika` remain marked for expert confirmation.

Objective gates are separate from human verdicts:

- automatic hard gates: schema validity, cost cap, bracket violations, locked glossary violations, known per-item unsupported insertion strings, known `accenti` omission;
- operator review: readability and literal-regression judgment;
- scholar review: fidelity, negation scope, and general content omission.

The D-arm recommendation remains `pending_operator_and_scholar_review` until the review sheet is filled. The tool must not auto-adopt v2.2 from metrics alone.

Operator sequence for D:

```bash
./venv/bin/python -m backend.pali.scripts.run_natural_ko_calibration_smoke \
  --out data/reports/pali/natural_ko_calibration_v2_2 \
  --calibration-source-dir data/reports/pali/natural_ko_calibration_v1 \
  --preflight-v2-2 \
  --pretty

./venv/bin/python -m backend.pali.scripts.run_natural_ko_calibration_smoke \
  --out data/reports/pali/natural_ko_calibration_v2_2 \
  --calibration-source-dir data/reports/pali/natural_ko_calibration_v1 \
  --submit-arm D \
  --pretty

./venv/bin/python -m backend.pali.scripts.run_natural_ko_calibration_smoke \
  --out data/reports/pali/natural_ko_calibration_v2_2 \
  --calibration-source-dir data/reports/pali/natural_ko_calibration_v1 \
  --poll \
  --pretty

./venv/bin/python -m backend.pali.scripts.run_natural_ko_calibration_smoke \
  --out data/reports/pali/natural_ko_calibration_v2_2 \
  --calibration-source-dir data/reports/pali/natural_ko_calibration_v1 \
  --fetch \
  --pretty

./venv/bin/python -m backend.pali.scripts.run_natural_ko_calibration_smoke \
  --out data/reports/pali/natural_ko_calibration_v2_2 \
  --calibration-source-dir data/reports/pali/natural_ko_calibration_v1 \
  --parse \
  --pretty

./venv/bin/python -m backend.pali.scripts.run_natural_ko_calibration_smoke \
  --out data/reports/pali/natural_ko_calibration_v2_2 \
  --calibration-source-dir data/reports/pali/natural_ko_calibration_v1 \
  --compare-v2-2 \
  --pretty
```

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
