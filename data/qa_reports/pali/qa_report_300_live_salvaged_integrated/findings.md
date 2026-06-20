# Pāli QA Findings Classifier v1

## Purpose

This local deterministic classifier decomposes broad `contains_untranslated_pali` signals into narrower allowed-display and strict-review signals. It does not modify translations and does not certify translation correctness.

Important caveat: Auto-allowed items are flag-level false positives, not certified-correct translations. Translation correctness remains tracked separately through gold/holdout regression, sampling, oracle comparison where available, and later human/expert review.

## Input Files

- review queue: `data/qa_reports/pali/qa_report_300_live_salvaged_integrated/review_queue.json`
- parsed salvaged: `data/reports/pali/pilot_300_batch/pilot_300_batch_parsed_salvaged.json`
- review report: `data/qa_reports/pali/qa_report_300_live_salvaged_integrated/review_report.md`

## Summary

- human-needed before: 79
- effective human-needed after: 12
- auto_accept_with_display_policy: 65
- possible_untranslated_pali_strict: 0
- grammar_uncertain retained: 11
- grammar_uncertain auto-accepted: 0

## Run Coverage Summary

- total Pāli runs detected: 732
- covered Pāli runs: 732
- uncovered Pāli runs: 0
- run worst-case failures: 0
- signal worst-case failures: 12

## contains_untranslated_pali Reclassification

contains_untranslated_pali was mostly false positive in the 300 pilot. Most cases are parenthetical Pāli or commentarial grammar lemma citations. Strict untranslated Pāli candidates should be the only untranslated-Pāli items that remain human-needed.

## Allowed Parenthetical Pāli Examples

| stable_segment_key | run | context |
| --- | --- | --- |
| `vri:romn:abh03t.tik:5ce9d8787e18` | `paṭiloma` | 그러나 역관(paṭiloma)에서는, 순관(anuloma)에서 "일어날 것이다, 멸할 것이다"라고 미래의 일어남과 멸함이 그 자체의 형 |
| `vri:romn:s0102t.tik:691b6cc86c16` | `ettha panā` | 들을 취하지 않은 이유를 묻고 대답하고자 하여, 먼저 그것들이 취해져야 할 방식을 보여주며 "그런데 여기서(ettha panā)" 등을 말했다. 눈앞에 있는 현재의 존재를 첫 번째로 취하고, 그 직후에 미래를 "두 번째"라고 취함에  |
| `vri:romn:s0201t.tik:cfd6c2db8704` | `samāna` |  의한 것"이므로, 고발당한 자와 고발자의 동등함은 범계를 저지른 상태에 의한 것이라고 하여 "'동등한 자(samāna)'란 '죄가 있는 자(sāpattika)'이다"라고 말했다. 그가 오직 상대방이 있는 자에 의해서만 고발되 |
| `vri:romn:s0302t.tik:75cb6eb45b34` | `mahāmukhaukkhalīnaṃ` | '큰 입구의 솥들의(mahāmukhaukkhalīnaṃ)'라는 것은 큰 입구를 가진 큰 항아리 백 개를 말한다. '탁월한 음식으로 가득 찬(paṇītabhojan |
| `vri:romn:vin02a1.att:b56ffa453013` | `dukkaṭa` | 다면, (발우를 다시) 수여받고 탁발 음식을 받아야 한다. 수여받지 않고 음식을 받는 자에게는 율의 악작죄(dukkaṭa)가 성립한다. 그러나 그것을 다시 수여받고 먹는 자에게는 범죄가 되지 않는다. 그러나 만약 비구가 "(발우 |

## Allowed Grammar Quote Examples

| stable_segment_key | run | context |
| --- | --- | --- |
| `vri:romn:vin02a2.att:bfbd7f00efd4` | `Jiridanti` | 은 고기를 먹는 자는 그도 그 업의 상속자가 되며, 도살자와 같이 그에게도 살생의 업이 된다는 의도이다. 'Jiridanti'라는 것은, 비방하는 자들은 소멸하지 않는다(na jiranti), 비방의 끝에 도달하지 않는다는 뜻이다. |
| `vri:romn:abh02t.tik:cbde70ef5c5b` | `na appiyanti` | 'na appiyanti'라는 것은 가지 않고, 들어가지 않는다는 뜻이다. 'anatthaṃ'이라는 것은 파멸, 또는 괴로움이다.  |
| `vri:romn:s0101t.tik:0a9d7d33330f` | `Sikkhā ekā` | 'Sikkhā ekā'라는 구절에서, 'sikkhā'는 도구격 의미의 주격 단어이고, 'eka'라는 단어는 '어떤 이들은 이와  |
| `vri:romn:s0103t.tik:2be1cfdd6a97` | `Atthi kho` | 192. 'Atthi kho'(있기는 참으로)에서 여기서 'kho'라는 단어는 질문에 [해당한다]. 'atthi nu'(과연 있는가?) |
| `vri:romn:s0401t.tik:a765b2b09bc0` | `Kāraṇamahantattā` | 'Sabhāvapakatikā(고유한 본성인)'라는 것은 고유한 성질이 된, 인위적이지 않은 본성이다. 'Kāraṇamahantattā(원인이 크기 때문에)'라는 것은 원인들의 큼에 의해서이니, 바라밀이라 불리는 원인들인 위대한 부처를 만드는 |

## Allowed Lemma Discussion Examples

| stable_segment_key | run | context |
| --- | --- | --- |
| `vri:romn:abh02t.tik:cbde70ef5c5b` | `a` | samāsa)로도 적용되었다. 왜냐하면 "태양을 보지 못하는 얼굴들" 등에서처럼, 복합어가 된 그것을 이 'a' 글자가 부정하는 것이 아니기 때문이다. 어떤 두려움 없는 상태에 대해서든 'yogakkhema'라는 단어 |
| `vri:romn:s0101t.tik:0a9d7d33330f` | `sikkhā ekā saññā uppajjanti` | 서와 같이 '어떤(ekacca)'의 동의어이며, 숫자를 나타내는 단어가 아니라고 (주석서에서) 말했다. ''sikkhā ekā saññā uppajjanti'는 '학습에 의해 어떤 인식들이 일어난다'는 뜻이다'라고. 나머지 구절들에서도 이와 같은 방법이다. |
| `vri:romn:s0103t.tik:2be1cfdd6a97` | `Diṭṭhipaññattiyā` | 데 여기서 말해져야 할 것, 그것은 『범망경 복주석』(brahmajālaṭīkā)에서 설해진 그대로이다. 'Diṭṭhipaññattiyā'(견해의 시설에 있어서)란 견해의 시설함에 있어서, "이와 같이 이 견해가 일어났다"라고 그 견해에 대해  |
| `vri:romn:s0509a.att:038f86a9ee32` | `avasāya` | ndajātā)'라는 것은 최상의 과를 위해 열의가 생긴 자이다. '끝마친 자(avasāyī)'라는 것은, avasāya는 끝(avasāna), 마침(niṭṭhāna)을 말하는데, 그것도 감각적 욕망들에 얽매이지 않은 마음을 가 |
| `vri:romn:s0513a3.att:284722dc0cd8` | `Narānamārāmakarāsu` | 'Narānamārāmakarāsu'라는 이 자따까의 상세한 이야기는 꾸날라 자따까(jā. 2.21.kuṇālajātaka)에서 명백해질 것이 |

## possible_untranslated_pali_strict Candidates

None.

## grammar_uncertain Retained

| stable_segment_key | hint | reasons |
| --- | --- | --- |
| `vri:romn:s0102t.tik:691b6cc86c16` | `possible_high` | `compound_interpretation_keyword, doctrinal_term_keyword` |
| `vri:romn:s0201t.tik:cfd6c2db8704` | `possible_high` | `negation_scope_keyword, quotation_or_particle_keyword` |
| `vri:romn:s0302t.tik:75cb6eb45b34` | `possible_high` | `quotation_or_particle_keyword` |
| `vri:romn:vin02a1.att:b56ffa453013` | `possible_high` | `quotation_or_particle_keyword` |
| `vri:romn:vin02a2.att:bfbd7f00efd4` | `possible_high` | `quotation_or_particle_keyword` |
| `vri:romn:abh03m11.mul:4ab6e93ef3c3` | `possible_high` | `negation_scope_keyword, quotation_or_particle_keyword` |
| `vri:romn:s0403t.tik:0b44a6389758` | `possible_high` | `compound_interpretation_keyword, negation_scope_keyword` |
| `vri:romn:s0513m.mul:545a4ef14103` | `possible_high` | `quotation_or_particle_keyword` |
| `vri:romn:s0514m.mul:88650af1ca41` | `possible_high` | `quotation_or_particle_keyword` |
| `vri:romn:s0519m.mul:f43a9c761757` | `possible_high` | `compound_interpretation_keyword, doctrinal_term_keyword, quotation_or_particle_keyword` |
| `vri:romn:vin01t2.tik:46bf2dc6b638` | `possible_high` | `compound_interpretation_keyword` |

## needs_expert_review Candidates

| stable_segment_key | reason |
| --- | --- |
| `vri:romn:s0102t.tik:691b6cc86c16` | `possible_high` |
| `vri:romn:s0201t.tik:cfd6c2db8704` | `possible_high` |
| `vri:romn:s0302t.tik:75cb6eb45b34` | `possible_high` |
| `vri:romn:vin02a1.att:b56ffa453013` | `possible_high` |
| `vri:romn:vin02a2.att:bfbd7f00efd4` | `possible_high` |
| `vri:romn:abh03m11.mul:4ab6e93ef3c3` | `possible_high` |
| `vri:romn:s0403t.tik:0b44a6389758` | `possible_high` |
| `vri:romn:s0513m.mul:545a4ef14103` | `possible_high` |
| `vri:romn:s0514m.mul:88650af1ca41` | `possible_high` |
| `vri:romn:s0519m.mul:f43a9c761757` | `possible_high` |
| `vri:romn:vin01t2.tik:46bf2dc6b638` | `possible_high` |

## QA Rule Improvement Recommendation

- Add deterministic allowed-Pāli rules into the main QA pipeline after this classifier is reviewed.
- Keep grammar_uncertain in the human review queue; classifier hints are ordering aids only.
- Add sampling guard for auto-allowed items in the next batch.

## Sampling Guard

- auto-allowed count: 67
- recommended sample size: 10
- sample seed: 3189920949
- stratification: decision, subsignal, text_layer

## Next Step

1. Review this classifier output before integrating allowed-Pāli rules into the main QA pipeline.
2. Re-run 300 QA after integration and measure human-needed reduction.
3. Add response_schema micro-smoke before the 1,000 pilot.
4. Add second-model verifier only for unresolved/high-risk subset after deterministic false positives are reduced.
