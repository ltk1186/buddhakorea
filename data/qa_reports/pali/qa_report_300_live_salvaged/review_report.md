# Pāli QA Review Report v1.2

이 보고서는 local-only deterministic QA 산출물입니다. Prompt/API/DB/RAG/UI 작업을 수행하지 않았습니다.

## Summary

- execution mode: `single_run`
- regression mode: disabled
- total segments: 300
- schema valid / invalid: 300 / 0
- parse failed: 0
- Priority counts: {'B': 12, 'C': 67}
- auto-resolvable groups: 0
- human-needed groups: 79
- estimated human review minutes: 103
- source integrity gaps: {'missing_field:display_source_text': 300, 'missing_field:normalization_notes': 300, 'missing_field:raw_source_text': 300, 'missing_field:translation_source_text': 300}
- oracle availability: {'oracle_unavailable': 203, 'second_model_verifier_candidate': 97}
- run manifest: `data/qa_reports/pali/qa_report_300_live_salvaged/run_manifest.json`

Oracle 일치 = 정답 확정이 아니며, oracle 불일치 = 오역 확정이 아닙니다. 불일치는 review queue로 올리는 triage signal일 뿐입니다.

## Auto-Resolvable Summary

- none

## Human-Needed Queue

### B · contains_untranslated_pali:vri:romn:abh03t.tik:5ce9d8787e18

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:abh03t.tik:5ce9d8787e18']
- signals: ['contains_untranslated_pali', 'needs_human_review']
- suggested_action: human_review
- estimated_review_minutes: 3
- review_tier: tier_1_operator

### B · contains_untranslated_pali:vri:romn:s0102t.tik:691b6cc86c16

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0102t.tik:691b6cc86c16']
- signals: ['contains_untranslated_pali', 'grammar_uncertain']
- suggested_action: human_review
- estimated_review_minutes: 3
- review_tier: tier_1_operator

### B · contains_untranslated_pali:vri:romn:s0201t.tik:cfd6c2db8704

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0201t.tik:cfd6c2db8704']
- signals: ['contains_untranslated_pali', 'grammar_uncertain']
- suggested_action: human_review
- estimated_review_minutes: 3
- review_tier: tier_1_operator

### B · contains_untranslated_pali:vri:romn:s0302t.tik:75cb6eb45b34

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0302t.tik:75cb6eb45b34']
- signals: ['contains_untranslated_pali', 'grammar_uncertain']
- suggested_action: human_review
- estimated_review_minutes: 3
- review_tier: tier_1_operator

### B · contains_untranslated_pali:vri:romn:vin02a1.att:b56ffa453013

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:vin02a1.att:b56ffa453013']
- signals: ['contains_untranslated_pali', 'grammar_uncertain']
- suggested_action: human_review
- estimated_review_minutes: 3
- review_tier: tier_1_operator

### B · contains_untranslated_pali:vri:romn:vin02a2.att:bfbd7f00efd4

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:vin02a2.att:bfbd7f00efd4']
- signals: ['contains_untranslated_pali', 'grammar_uncertain']
- suggested_action: human_review
- estimated_review_minutes: 3
- review_tier: tier_1_operator

### B · grammar_uncertain:vri:romn:abh03m11.mul:4ab6e93ef3c3

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:abh03m11.mul:4ab6e93ef3c3']
- signals: ['grammar_uncertain']
- suggested_action: human_review
- estimated_review_minutes: 3
- review_tier: tier_1_operator

### B · grammar_uncertain:vri:romn:s0403t.tik:0b44a6389758

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0403t.tik:0b44a6389758']
- signals: ['grammar_uncertain']
- suggested_action: human_review
- estimated_review_minutes: 3
- review_tier: tier_1_operator

### B · grammar_uncertain:vri:romn:s0513m.mul:545a4ef14103

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0513m.mul:545a4ef14103']
- signals: ['grammar_uncertain']
- suggested_action: human_review
- estimated_review_minutes: 3
- review_tier: tier_1_operator

### B · grammar_uncertain:vri:romn:s0514m.mul:88650af1ca41

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0514m.mul:88650af1ca41']
- signals: ['grammar_uncertain']
- suggested_action: human_review
- estimated_review_minutes: 3
- review_tier: tier_1_operator

### B · grammar_uncertain:vri:romn:s0519m.mul:f43a9c761757

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0519m.mul:f43a9c761757']
- signals: ['grammar_uncertain']
- suggested_action: human_review
- estimated_review_minutes: 3
- review_tier: tier_1_operator

### B · grammar_uncertain:vri:romn:vin01t2.tik:46bf2dc6b638

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:vin01t2.tik:46bf2dc6b638']
- signals: ['grammar_uncertain']
- suggested_action: human_review
- estimated_review_minutes: 3
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:abh01t.tik:b3a5c3bac60d

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:abh01t.tik:b3a5c3bac60d']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:abh01t.tik:e0aa59809338

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:abh01t.tik:e0aa59809338']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:abh02a.att:99a218804bc5

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:abh02a.att:99a218804bc5']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:abh02t.tik:38d55f5aef7a

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:abh02t.tik:38d55f5aef7a']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:abh02t.tik:cbde70ef5c5b

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:abh02t.tik:cbde70ef5c5b']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:abh02t.tik:e2b12856db46

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:abh02t.tik:e2b12856db46']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:abh03t.tik:b185546846c3

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:abh03t.tik:b185546846c3']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:abh03t.tik:ed07c66b0311

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:abh03t.tik:ed07c66b0311']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:e0103n.att:355746de2b2a

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:e0103n.att:355746de2b2a']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:e0104n.att:4f746e67fa49

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:e0104n.att:4f746e67fa49']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0101t.tik:0a9d7d33330f

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0101t.tik:0a9d7d33330f']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0101t.tik:14f01d855b04

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0101t.tik:14f01d855b04']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0101t.tik:21baebababdc

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0101t.tik:21baebababdc']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0101t.tik:3ed5afb93a71

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0101t.tik:3ed5afb93a71']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0101t.tik:d2e2c2826c6d

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0101t.tik:d2e2c2826c6d']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0102a.att:833e109e17d3

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0102a.att:833e109e17d3']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0102t.tik:3dd32d21880a

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0102t.tik:3dd32d21880a']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0103t.tik:2be1cfdd6a97

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0103t.tik:2be1cfdd6a97']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0201t.tik:6872e4b62d4b

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0201t.tik:6872e4b62d4b']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0201t.tik:732e56d7e791

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0201t.tik:732e56d7e791']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0201t.tik:7c03b0a5bdc5

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0201t.tik:7c03b0a5bdc5']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0202t.tik:3f72a66be753

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0202t.tik:3f72a66be753']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0202t.tik:4d7f6125f3f5

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0202t.tik:4d7f6125f3f5']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0202t.tik:bcc8233c219b

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0202t.tik:bcc8233c219b']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0203t.tik:58781e65df6a

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0203t.tik:58781e65df6a']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0301t.tik:635b9f107fd5

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0301t.tik:635b9f107fd5']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0301t.tik:9b035b2c66f0

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0301t.tik:9b035b2c66f0']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0302t.tik:521aa5cd0ea3

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0302t.tik:521aa5cd0ea3']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0302t.tik:99fa4fb3f39e

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0302t.tik:99fa4fb3f39e']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0303t.tik:1362b2dde10a

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0303t.tik:1362b2dde10a']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0303t.tik:138b61121f66

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0303t.tik:138b61121f66']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0304t.tik:68f695149cf7

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0304t.tik:68f695149cf7']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0305t.tik:06cc4695c02b

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0305t.tik:06cc4695c02b']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0305t.tik:f985488968a4

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0305t.tik:f985488968a4']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0401t.tik:17f84e8ea364

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0401t.tik:17f84e8ea364']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0401t.tik:a765b2b09bc0

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0401t.tik:a765b2b09bc0']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0402a.att:a4c3b70768ea

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0402a.att:a4c3b70768ea']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0402a.att:efa7d33f7272

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0402a.att:efa7d33f7272']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0402t.tik:48d47702d5bf

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0402t.tik:48d47702d5bf']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0403a.att:3a2c6c80bebc

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0403a.att:3a2c6c80bebc']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0403t.tik:00636ccf4093

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0403t.tik:00636ccf4093']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0403t.tik:b8d8b0c2146c

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0403t.tik:b8d8b0c2146c']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0403t.tik:eea3670bb80c

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0403t.tik:eea3670bb80c']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0404a.att:1ea869519213

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0404a.att:1ea869519213']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0503a.att:fb50026a0b4f

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0503a.att:fb50026a0b4f']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0505a.att:13574abc1c7e

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0505a.att:13574abc1c7e']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0505a.att:8707b45495cb

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0505a.att:8707b45495cb']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0505a.att:cff48b1cdf6f

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0505a.att:cff48b1cdf6f']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0505a.att:eef408281f45

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0505a.att:eef408281f45']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0506a.att:eeb53adb2177

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0506a.att:eeb53adb2177']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0508a1.att:8b9574445272

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0508a1.att:8b9574445272']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0508a1.att:f22d04078fa5

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0508a1.att:f22d04078fa5']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0509a.att:038f86a9ee32

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0509a.att:038f86a9ee32']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0513a1.att:51118d2e3575

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0513a1.att:51118d2e3575']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0513a3.att:284722dc0cd8

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0513a3.att:284722dc0cd8']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0514a2.att:9952800aaad1

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0514a2.att:9952800aaad1']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0515a.att:d24c7e329f13

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0515a.att:d24c7e329f13']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:s0519a.att:926904b81bfc

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:s0519a.att:926904b81bfc']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:vin01a.att:08cbe3d88a96

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:vin01a.att:08cbe3d88a96']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:vin01a.att:89f8b2bfc7e5

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:vin01a.att:89f8b2bfc7e5']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:vin01t1.tik:e790c326e294

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:vin01t1.tik:e790c326e294']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:vin01t2.tik:502e2d712344

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:vin01t2.tik:502e2d712344']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:vin02a1.att:e5f5ffcdaed1

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:vin02a1.att:e5f5ffcdaed1']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:vin02a2.att:0b9fb56d898f

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:vin02a2.att:0b9fb56d898f']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:vin02a2.att:b43558c74699

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:vin02a2.att:b43558c74699']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:vin02t.tik:c104fc1e41ea

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:vin02t.tik:c104fc1e41ea']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

### C · contains_untranslated_pali:vri:romn:vin02t.tik:f4af162dcc24

- recurrence_count: 1
- example stable_segment_keys: ['vri:romn:vin02t.tik:f4af162dcc24']
- signals: ['contains_untranslated_pali']
- suggested_action: human_review
- estimated_review_minutes: 1
- review_tier: tier_1_operator

## Representative Sample Package

### random
- `vri:romn:abh03t.tik:1c4cd2a168ad` · tika · prose · short
- `vri:romn:s0101t.tik:3ed5afb93a71` · tika · prose · long
- `vri:romn:s0305t.tik:f985488968a4` · tika · prose · long
- `vri:romn:s0402a.att:a4c3b70768ea` · atthakatha · prose · long
- `vri:romn:vin02a1.att:e5f5ffcdaed1` · atthakatha · prose · medium

### long
- `vri:romn:s0202t.tik:4d7f6125f3f5` · tika · prose · long
- `vri:romn:s0202t.tik:bcc8233c219b` · tika · prose · long
- `vri:romn:s0301t.tik:9b035b2c66f0` · tika · prose · long
- `vri:romn:s0402a.att:a4c3b70768ea` · atthakatha · prose · long
- `vri:romn:s0403t.tik:b8d8b0c2146c` · tika · prose · long

### verse
- `vri:romn:s0403t.tik:0b44a6389758` · tika · verse · medium
- `vri:romn:s0508a1.att:1233433564d1` · atthakatha · verse · short
- `vri:romn:s0508m.mul:f90c9806366a` · mula · verse · short
- `vri:romn:s0510m2.mul:6210bd21c95f` · mula · verse · short
- `vri:romn:vin02m4.mul:d49c727cc20c` · mula · verse · short

### tika
- `vri:romn:s0201t.tik:ad1304f9ee55` · tika · prose · medium
- `vri:romn:s0302t.tik:521aa5cd0ea3` · tika · prose · long
- `vri:romn:s0305t.tik:06cc4695c02b` · tika · prose · long
- `vri:romn:s0305t.tik:67c7836ad2e0` · tika · prose · long
- `vri:romn:vin01t2.tik:195c065cc5d3` · tika · prose · short

### title
- none

### citation_heavy
- `vri:romn:abh02a.att:99a218804bc5` · atthakatha · prose · long
- `vri:romn:s0101t.tik:0a9d7d33330f` · tika · prose · medium
- `vri:romn:s0103t.tik:93a37cfe8915` · tika · prose · medium
- `vri:romn:s0504a.att:f7749494d902` · atthakatha · verse · medium
- `vri:romn:s0519a.att:926904b81bfc` · atthakatha · prose · long

## Gold Results

### Holdout Correctness

- pass/fail/escalate: 0 / 0 / 0
- gold entries not present in this run: 9
- holdout_gold는 regression_gold와 합산하지 않습니다.

### Regression Canary

- current pass/fail/escalate: 0 / 0 / 0
- gold entries not present in this run: 9
- regression mode disabled: before/after verdict는 계산하지 않았습니다.

## Correctness Triage Candidates

- oracle_unavailable: 203
- second_model_verifier_candidate: 97

이번 단계에서는 CC0 parallel comparison, copyright eyes-only reference, second-model verifier live 호출을 실행하지 않습니다.
aṭṭhakathā / ṭīkā는 제외하지 않고 `oracle_unavailable`로 표시합니다.
