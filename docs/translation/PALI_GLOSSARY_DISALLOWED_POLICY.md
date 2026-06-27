# Pāli Glossary Disallowed Rendering Policy

This policy governs deterministic glossary QA for Pāli translation outputs. It does not change translations, preferred renderings, prompts, source XML, or the response schema.

## Enforcement Tiers

Disallowed Korean renderings are not all equal. The QA checker uses three tiers:

- `hard`: A triggered disallowed rendering is a hard glossary violation.
- `aligned_hard`: A triggered disallowed rendering is hard only when `terms[]` maps the relevant Pāli term to a Korean value containing that disallowed rendering. If the Korean phrase appears elsewhere without that terms alignment, it is advisory.
- `advisory`: The finding is reported as a warning only and does not affect the objective gate.

The practical alignment signal is `terms[]`. Full source-to-target window alignment is not implemented yet.

## Audit Rule

Use `hard` for distinctive, low-collision bad calques or doctrinally unsafe phrases. Use `aligned_hard` or `advisory` for high-frequency single Korean words that may be legitimate translations of other Pāli expressions in the same segment.

## Current Decisions

| Pāli | Preferred / canonical | Disallowed | Tier | Reason |
|---|---|---|---|---|
| `khandha` | `무더기` | `무리` | `aligned_hard` | `무리` is a common Korean word and may translate another source expression such as a group or crowd. It is hard only when `terms[]` maps `khandha` to `무리`. |
| `paññuttara` | `통찰지를 으뜸으로 삼는`, `통찰지를 최상으로 삼는` | `통찰지를 위로` | `hard` | Distinctive multi-token calque with low legitimate-collision risk. |
| `ādibhāva` | `처음이 됨`, `시작이 됨`, `시작으로서의 성격` | `처음-상태` | `hard` | Distinctive bad calque. |
| `kammārāmatā` | `일을 즐김` | `세속적인 일을 즐김` | `hard` | Adds unsupported qualifier. |
| `khārena paripphositvā` | `잿물을 뿌리고서` | `상처에 잿물`, `상처에 잿물을 뿌리고서` | `hard` | Adds unsupported object/location. |
| `nanabhāvanāya / nasaraṇaṃ` risk class | Preserve double-negation logic | `번뇌를 동반`, `번뇌를 동반하지 않으며` | `hard` | Known Paṭṭhāna negation-scope risk. |
| `yama`, `niyama`, `viññatti`, `otaraṇā`, `ājīvika`, `appavatti`, `kalyāṇamitta` | Context dependent | Context-specific disallowed phrases | `advisory` | Needs expert confirmation before production glossary promotion. |

## khandha Policy

The canonical rendering remains:

```text
khandha -> 무더기
```

`무리` is not globally banned. It becomes a hard glossary violation only when the model itself maps `khandha` to `무리` in `terms[]`. If a segment contains `khandha` but the `terms[]` mapping is `khandha -> 무더기`, while `무리` appears elsewhere in the Korean body for another source expression, the finding is advisory only.

## Bracket Policy

Bracket QA is source-aware:

- `SOURCE_FAITHFUL`: the bracket span or its content appears in `original_text`; allowed, non-gating.
- `SUPPLIED_KOREAN`: bracketed Korean not present in source; retry-only gating.
- `SUPPLIED_NUMBER`: bracketed number not present in source; advisory.
- `HANJA_GLOSS`: bracketed CJK/Hanja not present in source; advisory.
- `OTHER_BRACKET`: Latin/mixed/other bracket content; advisory.

Only `SUPPLIED_KOREAN` brackets enter the retry-only gate.

## Roadmap

Future QA can replace `terms[]` alignment with source-target window alignment. Until then, `terms[]` is the conservative alignment evidence used to avoid high-frequency substring false positives at 1,000/200k scale.

