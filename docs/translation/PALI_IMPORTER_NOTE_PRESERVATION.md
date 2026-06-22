# Pāli Importer Note Preservation

## Purpose

Step 3F proved that VRI XML `<note>` apparatus can provide useful QA/review evidence, but it required reparsing source XML after the 300 pilot. That is acceptable for a small pilot. At 1,000+ scale, the importer should preserve source apparatus structurally during ingest so downstream QA and internal review tooling can use it without post-hoc source-file recovery.

## Core Principle

`source_apparatus` is source metadata.

It is not translation prompt input. It must not be mixed into `original_text`, `normalized_text`, or any translation request payload.

This pipeline remains apparatus-aware QA/review, not apparatus-aware translation.

## Additive-Only Contract

The importer preserves `<note>` data as a new optional segment field:

```json
{
  "source_apparatus": [
    {
      "note_type": "variant",
      "is_variant_apparatus": true,
      "raw_note_text": "antaṃ niṭṭhaṃ (sī.)",
      "variant_text": "antaṃ niṭṭhaṃ",
      "sigla": ["sī"],
      "citation_refs": [],
      "anchor_text": "accantadiṭṭhaṃ",
      "xml_node_path": "...",
      "char_offset": 0,
      "evidence_strength_hint": "named_witness",
      "auto_apply": false
    }
  ]
}
```

The following must remain stable:

- `original_text`
- `stable_segment_key`
- `source_path`
- `xml_node_paths`
- segment boundary
- `source_text_hash`
- translation prompt input

Only `source_apparatus` may be added.

## Classification Rules

The importer reuses Step 3F parsing logic from `backend/pali/translation/variant_apparatus.py`. It does not duplicate the variant/citation classifier.

Supported note types:

- `variant`
- `citation`
- `peyyala`
- `editorial`
- `unknown`

Citation notes are not variant apparatus. In particular:

```text
ma. ni. 1.55
```

is a Majjhima Nikāya citation reference, not a Myanmar/Burmese `ma.` variant siglum.

Variant notes such as:

```text
antaṃ niṭṭhaṃ (sī.)
```

are preserved as variant apparatus with `is_variant_apparatus=true`.

## Evidence Caveat

Variant apparatus is attestation, not proof.

The VRI main text remains the editor-selected reading. Variants are never auto-applied by the importer. Any future adoption of a variant reading must happen in a reviewed step with explicit provenance.

## Prompt Boundary

Current translation prompt rendering uses `normalized_text` or `original_text`. `source_apparatus` is not included.

Future experiments may test apparatus-aware context, but that must be a separate approved step. The default importer behavior is metadata preservation only.

## Verification

Run:

```bash
./venv/bin/python -m backend.pali.scripts.check_importer_note_preservation \
  --source-root data/tipitaka-xml \
  --out data/reports/pali/importer_note_preservation_check.json \
  --pretty
```

The check reparses representative local files twice:

1. legacy projection with `preserve_source_apparatus=false`
2. current importer with `preserve_source_apparatus=true`

It fails if any non-additive change appears in segment count, stable keys, source hashes, original text, XML paths, or translation prompt input.

## Non-Goals

Step 3H does not:

- call Gemini/API/LLM/Batch/network
- modify translated outputs
- regenerate 300 pilot translations
- modify source XML
- modify prompt templates
- modify glossary or gold set files
- freeze holdout gold
- select the 1,000 pilot
- auto-apply variant readings
