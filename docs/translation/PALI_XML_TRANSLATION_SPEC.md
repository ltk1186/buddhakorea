# Pali Studio VRI XML Canonical Segment and Token Count Spec

Status: intermediate implementation spec  
Scope: VRI XML parsing, canonical segment JSON artifacts, local token counting  
Out of scope: translation execution, text generation APIs, official price/cost analysis, DB migration, RAG, embedding, PDF diff

## 1. Purpose

Buddha Korea Pali Studio will use VRI XML from `VipassanaTech/tipitaka-xml` as the canonical source for Pali corpus ingest. The importer should produce a Buddha Korea Canonical Segment Format artifact that can be served as an original-text library before translation and can later support translation versions, correction, reader feedback, selective retranslation, and publication workflows.

The current goal is not to match old PDF parser segment boundaries. VRI XML is the new canonical basis.

### 1.1 PDF Diff and Cost Boundary

PDF diff is not part of this phase. Existing PDF-derived JSON can be kept as a legacy diagnostic source for historical comparison, but it must not define canonical segment boundaries and is not required for importer validation.

This phase also stops at token counts. Official provider pricing, total cost estimation, and scenario-based cost analysis are intentionally deferred to a later cost-profile step. The current artifact should make that later step possible by exposing stable segment counts, character counts, local GPT-family token estimates, and local Gemini-family approximate token estimates.

### 1.2 Local VRI Checkout

Repeated development should use a local shallow checkout under `data/tipitaka-xml`. This directory is intentionally ignored by Git because it is a large external source repository.

```bash
git clone --depth 1 https://github.com/VipassanaTech/tipitaka-xml.git data/tipitaka-xml
cd data/tipitaka-xml
git rev-parse HEAD
```

Use that commit SHA as `source_commit` whenever generating segment artifacts or corpus token summaries:

```bash
SOURCE_COMMIT=$(git -C data/tipitaka-xml rev-parse HEAD)

python3 backend/pali/importers/vri_xml.py \
  data/tipitaka-xml/romn/s0505a.att.xml \
  --source-path romn/s0505a.att.xml \
  --source-commit "$SOURCE_COMMIT" \
  --out /tmp/s0505a_segments.json \
  --pretty

python3 backend/pali/scripts/count_vri_corpus_tokens.py \
  --input-dir data/tipitaka-xml/romn \
  --include-layers mul,att,tik \
  --token-profiles config/pali_token_profiles.example.json \
  --source-commit "$SOURCE_COMMIT" \
  --out /tmp/vri_romn_corpus_token_summary.json \
  --pretty
```

## 2. Buddha Korea Canonical Segment Format

The Buddha Korea Canonical Segment Format is not raw VRI XML. It is a normalized source artifact designed for long-term application use.

Design goals:

- Re-importing the same XML file should preserve segment identity.
- Source provenance must be explicit: repository, commit, path, file, XML node path, canonical reference, and text hash.
- Segment boundaries should reflect VRI XML structure, not legacy PDF output.
- Headings, vagga/chapter, sutta/subsection, gatha, prose paragraph, page references, and notes should be preserved.
- `original_text` must contain translatable main text only, not `pb` or `note` apparatus text.
- Translation is not stored in this artifact.
- Later DB work can connect these segments to `translation_versions`, `segment_feedback`, and `translation_jobs`.

Top-level artifact:

```json
{
  "literature": {},
  "segments": [],
  "import_report": {},
  "token_report": {}
}
```

`token_report` is optional at import time, but supported by the prototype.

## 3. VRI XML Sampling Results

Local `tipitaka-xml` checkout was not present in this workspace. Samples were fetched from the GitHub repository for structural inspection, prioritizing `romn`.

### 3.1 Common Structure

Most inspected files use:

```xml
<TEI.2>
  <teiHeader/>
  <text>
    <front/>
    <body xml:space="preserve">
      ...
    </body>
  </text>
</TEI.2>
```

Common nodes:

- `div`: structural container in some files.
- `head`: heading inside `div` in some files.
- `p`: heading, prose, verse line, running title, or metadata depending on `rend`.
- `pb`: edition/page reference.
- `note`: variant, footnote, or apparatus note.
- `hi`: inline text; included in main text unless inside `note`.
- `trailer`: closing text; currently skipped by importer.

### 3.2 Sample Matrix

| source_path | book_code | text_layer | div/head structure | p/@rend structure | paragraph rend values observed | pb usage | note usage | importer policy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `romn/s0505m.mul.xml` | `s0505m` | `mula` | `div type="book"` and `div type="vagga"` | strong; sutta headings are `p rend="subhead"` | `nikaya`, `subhead`, `bodytext`, `hangnum`, `gatha1-3`, `gathalast`, `centre` | `M`, `V`, `P`, `T` | present | translate `bodytext` and grouped gatha; metadata headings/page/notes; skip most `centre` |
| `romn/s0505a.att.xml` | `s0505a` | `atthakatha` | no `div/head` in inspected sample | primary structure via `p/@rend` | `book`, `title`, `chapter`, `subhead`, `bodytext`, `indent`, `unindented`, `gatha1-3`, `gathalast`, `centre`, `nikaya` | `M`, `P`, `V` | not in sample stats | translate prose and grouped gatha; headings from `p/@rend`; skip running-title `centre` |
| `romn/s0101m.mul.xml` | `s0101m` | `mula` | `div type="book"` and `div type="sutta"` with `head` | subheads inside sutta as `p rend="subhead"` | `nikaya`, `bodytext`, `subhead`, `centre`, `gatha1-3`, `gathalast` | `T`, `P`, `M`, `V` | present | canonical refs can use internal `dn1_1` style ids |
| `romn/s0101a.att.xml` | `s0101a` | `atthakatha` | `div/head` present in inspected sample | paragraph structure still uses `p/@rend` | `bodytext`, `gatha1-3`, `gathalast`, `subhead`, `centre`, `indent`, `unindented`, `nikaya`, `subsubhead` | `P`, `M`, `V` | not prominent in sample stats | support both div/head and p-rend headings |
| `romn/s0101t.tik.xml` | `s0101t` | `tika` | `div/head` present in inspected sample | paragraph structure uses `p/@rend` | `bodytext`, `subhead`, `gatha1-3`, `gathalast`, `centre`, `indent`, `unindented`, `subsubhead`, `nikaya` | `M`, `V` | not prominent in sample stats | same dual-policy handling |
| `romn/vin01m.mul.xml` | `vin01m` | `mula` | `div type="book"`, `div type="kanda"` | paragraph/verse via `p/@rend` | `bodytext`, `centre`, `title`, `gatha1-3`, `gathalast`, `subhead`, `nikaya` | `T`, `V`, `M`, `P` | present | treat `kanda` as vagga/chapter-level parent |
| `romn/vin01a.att.xml` | `vin01a` | `atthakatha` | no `div/head` observed | primary p-rend structure | `bodytext`, `gatha1-3`, `gathalast`, `centre`, `subhead`, `indent`, `title`, `chapter`, `nikaya`, `book`, `unindented`, `subsubhead` | `P`, `M`, `V` | not prominent in sample stats | p-rend-only policy required |
| `romn/vin01t1.tik.xml` | `vin01t1` | `tika` | no `div/head` observed | primary p-rend structure | `bodytext`, `gatha1-3`, `gathalast`, `indent`, `unindented`, `centre`, `subhead`, `nikaya`, `book`, `subsubhead`, `title`, `chapter` | `M`, `V` | not prominent in sample stats | split tika part; filename part must be preserved |
| `romn/abh01m.mul.xml` | `abh01m` | `mula` | no `div/head` observed | primary p-rend structure | `bodytext`, `centre`, `subhead`, `title`, `unindented`, `chapter`, `nikaya`, `book` | `T`, `V`, `M`, `P` | present | Abhidhamma mula can be p-rend-only |
| `romn/abh01a.att.xml` | `abh01a` | `atthakatha` | no `div/head` observed | primary p-rend structure | `bodytext`, `gatha1-3`, `gathalast`, `subhead`, `centre`, `title`, `indent`, `chapter`, `nikaya`, `book`, `subsubhead` | `M`, `V`, `P` | not prominent in sample stats | p-rend-only policy required |
| `romn/abh01t.tik.xml` | `abh01t` | `tika` | no `div/head` observed | primary p-rend structure | `bodytext`, `subhead`, `centre`, `title`, `gatha1`, `gathalast`, `chapter`, `subsubhead`, `unindented`, `nikaya`, `book` | `M`, `V` | not prominent in sample stats | p-rend-only policy required |
| `romn/vin02a1.att.xml` | `vin02a1` | `atthakatha` | no `div/head` observed | primary p-rend structure | `bodytext`, `centre`, `subhead`, `gatha1-3`, `gathalast`, `title`, `indent`, `chapter`, `book`, `nikaya`, `unindented` | `M`, `V`, `P` | not prominent in sample stats | split-file numbering must be preserved in `book_code` |
| `romn/abh04t.nrf.xml` | `abh04t` | `nrf` | no `div/head` observed | primary p-rend structure | `bodytext`, `subhead`, `centre`, `title`, `indent`, `chapter`, `unindented`, `gatha1`, `gathalast`, `nikaya`, `book`, `subsubhead` | `M`, `V` | not prominent in sample stats | `nrf` meaning needs human confirmation before production inclusion |

### 3.3 Translation Target Nodes

Translate as segments:

- `p rend="bodytext"`
- `p rend="indent"`
- `p rend="unindented"`
- contiguous `p rend="hangnum"` plus `p rend="gatha*"` grouped as one verse segment
- contiguous `p rend="gatha*"` grouped until `gathalast`

Metadata-only:

- `head`
- `p rend="nikaya"`
- `p rend="book"`
- `p rend="title"`
- `p rend="chapter"`
- `p rend="subhead"`
- `p rend="subsubhead"`
- `pb`
- `note`

Skipped by default:

- `p rend="centre"` because it is often invocation, running title, or repeated display text.
- `trailer`.

Human review needed:

- Whether some `centre` paragraphs are real content.
- Whether notes should later be separate translatable apparatus segments.
- Exact meaning and inclusion policy for `.nrf.xml`.

## 4. Filename and Layer Policy

Observed filename pattern:

```text
{prefix}{number}{layer_letter}{part}.{suffix}.xml
```

Examples:

- `s0505m.mul.xml`
- `s0505a.att.xml`
- `s0101t.tik.xml`
- `vin01t1.tik.xml`
- `vin02a1.att.xml`
- `abh03m1.mul.xml`
- `abh04t.nrf.xml`

Current inference:

- `prefix`: `vin`, `s`, `abh`, `e`.
- `pitaka`: `vinaya`, `sutta`, `abhidhamma`, `extra`.
- `text_layer`: suffix mapping `mul -> mula`, `att -> atthakatha`, `tik -> tika`, `nrf -> nrf`.
- `book_code`: filename stem before suffix, preserving split part, e.g. `vin02a1`.
- `script`: directory name, primarily `romn`.

Filename inference is necessary but insufficient. Internal headings and XML paths are still preserved.

## 5. Stable Segment Identity Policy

Candidates considered:

| Candidate | Strength | Weakness |
| --- | --- | --- |
| `source_path + xml_node_path` | Stable when XML structure is stable; survives text edits | Can change if upstream inserts/removes sibling nodes before an ordinal-only path |
| `source_path + sort_order` | Simple and repeatable for unchanged files | Fragile under inserted/deleted segments |
| `source_path + heading_path + local paragraph index` | More semantic for p-rend-only files | Heading text edits can shift identity |
| `source_path + canonical_ref + local index` | Good when `div/@n` or `p/@n` exists | Many commentarial prose paragraphs lack strong internal numbering |
| Hybrid with `source_text_hash` | Useful for reconciliation | Hash must not be the identity because text corrections would break feedback links |

Recommended v1 policy:

```text
stable_segment_key = "vri:{script}:{source_file_stem}:{sha1(source_path + xml_node_path)[0:12]}"
```

`source_text_hash = sha256(normalized_text)`.

Rationale:

- The key is independent of text content, so minor source text corrections do not sever translation or feedback linkage.
- `source_text_hash` detects source text drift.
- `canonical_ref`, `heading_path`, and `sort_order` support reconciliation if XML structure changes.

Known instability cases:

- p-rend-only files with ordinal XML paths can shift when upstream inserts a new paragraph before an existing paragraph.
- Heading edits can change fallback canonical refs.
- Verse regrouping policy changes can change grouped XML node paths.

When this happens, reconciliation should compare old/new `source_text_hash`, nearby `sort_order`, `heading_path`, `canonical_ref`, and normalized text similarity.

## 6. Segment JSON v1 Field Matrix

Storage recommendation values:

- `column-now-compatible`: maps to current `Literature` or `Segment` fields.
- `column-future`: should become a DB column or indexed field later.
- `metadata-now`: keep in JSONB/display metadata until stable.
- `derived`: useful in artifacts/reports but not necessarily stored.

| Field | Type | Required | Generation | Stability | Storage recommendation |
| --- | --- | --- | --- | --- | --- |
| `stable_segment_key` | string | yes | `source_path + xml_node_path` hash with VRI prefix | high for unchanged XML structure | `column-future`, unique |
| `literature_id` | string | yes | `vri-{script}-{source_file_stem}` | high | `column-now-compatible` |
| `literature_name` | string | yes | internal book/title heading, fallback `book_code` | medium | `column-now-compatible` |
| `pali_name` | string | yes | same as Pali internal title | medium | `column-now-compatible` |
| `source_repo` | string | yes | VRI repo URL | high | `metadata-now`, `column-future` |
| `source_commit` | string/null | production yes, prototype nullable | Git commit SHA | high | `column-future` |
| `source_path` | string | yes | repo-relative path | high | `column-future` |
| `source_file` | string | yes | basename | high | `metadata-now` |
| `script` | string | yes | source directory, e.g. `romn` | high | `metadata-now` |
| `pitaka` | string/null | recommended | filename prefix mapping | medium | `column-now-compatible` |
| `nikaya` | string/null | recommended for sutta | internal `nikaya`, fallback filename mapping | medium | `column-now-compatible` |
| `book_code` | string | yes | filename code preserving split part | high | `column-future` |
| `text_layer` | string | yes | suffix mapping | high | `column-future` |
| `canonical_ref` | string | yes | internal ids/numbers where available, fallback segment ref | medium | `column-future` |
| `sort_order` | integer | yes | 1-based segment order | high per import | `column-future` |
| `xml_node_path` | string | yes | stable path using `@n`/`@id`, ordinal fallback | medium to high | `column-future` |
| `heading_path` | array | yes | maintained from `div/head` and `p/@rend` headings | medium | `metadata-now` |
| `parent_key` | string/null | optional | hash of source path plus nearest parent id | medium | `column-future` |
| `chunk_type` | string | yes | `prose` or `verse` in prototype | high | `column-future` |
| `paragraph_number` | string/int/null | optional | `p/@n` or local counter | medium | `metadata-now`; current `paragraph_id` compatibility |
| `page_ref` | string/null | optional | first `pb` ref in segment | low to medium | `metadata-now` |
| `edition_ref` | array | optional | all segment `pb` refs | medium | `metadata-now` |
| `original_text` | string | yes | main text excluding `pb` and `note` | high | `column-now-compatible` |
| `normalized_text` | string | yes | whitespace-normalized original | high | `derived`, possible `column-future` |
| `source_text_hash` | string | yes | SHA-256 of `normalized_text` | high | `column-future`, indexed |
| `legacy_location` | object/null | optional | reserved for old imports | low | `metadata-now` |
| `vagga_id` | integer/null | optional | chapter/vagga/kanda heading number | medium | `column-now-compatible` |
| `vagga_name` | string/null | optional | chapter/vagga/kanda heading text | medium | `column-now-compatible` |
| `sutta_id` | integer/null | optional | sutta/subhead leading number | medium | `column-now-compatible` |
| `sutta_name` | string/null | optional | sutta/subhead text | medium | `column-now-compatible` |
| `paragraph_id` | integer | yes | local paragraph counter within current heading scope | medium | `column-now-compatible` |

## 7. Segment JSON v1 Example

```json
{
  "stable_segment_key": "vri:romn:s0505m.mul:60246498d319",
  "literature_id": "vri-romn-s0505m-mul",
  "source_path": "romn/s0505m.mul.xml",
  "text_layer": "mula",
  "canonical_ref": "kn5_1:1",
  "sort_order": 1,
  "xml_node_path": "/TEI.2/text[1]/body[1]/div[@n='kn5']/div[@n='kn5_1']/p[@n='1'] + ...",
  "heading_path": [
    {"level": 0, "type": "nikaya", "text": "Khuddakanikāye", "id": null},
    {"level": 1, "type": "book", "text": "Suttanipātapāḷi", "id": "kn5"},
    {"level": 3, "type": "vagga", "text": "1. Uragavaggo", "id": "kn5_1"},
    {"level": 5, "type": "subhead", "text": "1. Uragasuttaṃ", "id": null}
  ],
  "chunk_type": "verse",
  "original_text": "1. Yo uppatitaṃ vineti kodhaṃ ...",
  "source_text_hash": "..."
}
```

## 8. Importer Prototype

Implemented:

- `backend/pali/importers/vri_xml.py`

Key classes:

- `VriXmlImportConfig`
- `VriXmlParser`
- `VriXmlImportResult`
- `LiteratureArtifact`
- `SegmentArtifact`
- `ImportReport`

CLI:

```bash
python3 backend/pali/importers/vri_xml.py \
  data/tipitaka-xml/romn/s0505a.att.xml \
  --source-path romn/s0505a.att.xml \
  --source-commit <git-sha> \
  --out /tmp/s0505a_segments.json \
  --pretty
```

With token report:

```bash
python3 backend/pali/importers/vri_xml.py \
  data/tipitaka-xml/romn/s0505a.att.xml \
  --source-path romn/s0505a.att.xml \
  --source-commit <git-sha> \
  --out /tmp/s0505a_segments.json \
  --token-report /tmp/s0505a_token_report.json \
  --token-profiles config/pali_token_profiles.example.json \
  --pretty
```

## 9. Importer Validation Criteria

`import_report` includes:

- `total_segments`
- `segment_count_by_chunk_type`
- `unknown_node_count`
- `unknown_rend_values`
- `skipped_node_count`
- `metadata_only_node_count`
- `pb_only_node_count`
- `note_only_node_count`
- `skipped_empty_node_count`
- `note_count`
- `page_ref_count`
- `empty_text_segment_count`
- `empty_text_error_count`
- `empty_node_classification`
- `duplicate_source_text_hash_count`
- `headingless_segment_count`
- `largest_segments_by_chars`
- `verse_group_count`
- `verse_line_count`
- `sort_order_unique`
- `sort_order_contiguous`
- `notes_excluded_from_original_text`
- `page_refs_excluded_from_original_text`
- `warnings`
- `errors`

Validation expectations:

- Same file imported twice should produce the same `stable_segment_key` values.
- `sort_order` starts at 1 and is contiguous.
- Empty translatable `original_text` is an error only when the node appears to contain real translatable content that the importer removed incorrectly.
- `pb`-only, `note`-only, metadata-only, and whitespace-only candidates are skipped and counted separately rather than emitted as segments.
- `source_text_hash` is deterministic from `normalized_text`.
- Headingless segment count is reported for review.
- Duplicate source text hash count is reported.
- Page refs and notes are not mixed into `original_text`.
- Unknown `p/@rend` values become warnings.

### 9.1 Empty original_text Policy

Production importer policy:

- After removing `pb` and `note`, do not emit prose or verse segments with empty `original_text`.
- If a candidate node contains only page break references, increment `pb_only_node_count`.
- If it contains only notes, increment `note_only_node_count`.
- If it is a heading or other metadata-only node, update `heading_path` or increment `metadata_only_node_count`.
- If it is whitespace-only, increment `skipped_empty_node_count`.
- Keep `empty_text_error_count` only for nodes that look like true translation targets but still become empty.

### 9.2 Empty Text Analysis from VRI romn

Before the policy update, the files below produced empty segment candidate errors. Local full analysis of the current checkout found 550 empty candidates in these 10 files. They were all non-content candidates: whitespace-only separators, empty verse-number lines, empty verse-closing lines, or note-only references. None looked like real translatable text that the importer had incorrectly removed.

| source_path | count | tag | rend values | first xml_node_path examples | classification | decision |
| --- | ---: | --- | --- | --- | --- | --- |
| `romn/s0402a.att.xml` | 1 | `p` | `bodytext` | `/TEI.2/text[1]/body[1]/div[@n='an2']/div[@n='an2_3']/div[@n='an2_3_4']/p[9]` | whitespace-only | skip, no error |
| `romn/s0502m.mul.xml` | 1 | `p` | `bodytext` | `/TEI.2/text[1]/body[1]/div[@n='kn2']/p[4]` | note-only | count as `note_only_node_count`, no segment |
| `romn/s0513a1.att.xml` | 147 | `p` | `hangnum` | `/TEI.2/text[1]/body[1]/p[865]`, `/p[915]`, `/p[937]` | whitespace-only verse-number placeholders | skip, no error |
| `romn/s0513a2.att.xml` | 150 | `p` | `hangnum` | `/TEI.2/text[1]/body[1]/p[6]`, `/p[26]`, `/p[47]` | whitespace-only verse-number placeholders | skip, no error |
| `romn/s0513a3.att.xml` | 138 | `p` | `hangnum` | `/TEI.2/text[1]/body[1]/p[7]`, `/p[38]`, `/p[67]` | whitespace-only verse-number placeholders | skip, no error |
| `romn/s0513a4.att.xml` | 84 | `p` | `hangnum`, `gathalast` | `/TEI.2/text[1]/body[1]/p[6]`, `/p[54]`, `/p[126]` | whitespace-only verse placeholders | skip, no error |
| `romn/s0514a1.att.xml` | 17 | `p` | `hangnum` | `/TEI.2/text[1]/body[1]/p[3]`, `/p[210]`, `/p[438]` | whitespace-only verse-number placeholders | skip, no error |
| `romn/s0514a2.att.xml` | 5 | `p` | `hangnum` | `/TEI.2/text[1]/body[1]/p[6]`, `/p[497]`, `/p[1170]` | whitespace-only verse-number placeholders | skip, no error |
| `romn/s0514a3.att.xml` | 6 | `p` | `hangnum`, `gathalast` | `/TEI.2/text[1]/body[1]/p[6]`, `/p[845]`, `/p[1480]` | whitespace-only verse placeholders | skip, no error |
| `romn/s0515m.mul.xml` | 1 | `p` | `gathalast` | `/TEI.2/text[1]/body[1]/div[@n='kn15']/div[@n='kn15_15']/p[217]` | whitespace-only verse-closing placeholder | skip, no error |

## 10. Local Token Counting Design

Implemented:

- `backend/pali/tokenization/token_counter.py`
- `config/pali_token_profiles.example.json`

Profiles:

```json
{
  "profiles": [
    {
      "profile_id": "gpt_local_default",
      "provider": "openai",
      "counter": "tiktoken",
      "model": "CONFIGURED_LATER",
      "encoding_fallback": "cl100k_base"
    },
    {
      "profile_id": "gemini_local_approx",
      "provider": "gemini",
      "counter": "sentencepiece_or_heuristic",
      "sentencepiece_model_path": null
    }
  ]
}
```

GPT-family:

- Uses local `tiktoken`.
- If exact model is not configured or unknown to `tiktoken`, uses fallback encoding such as `cl100k_base`.
- Fallback is recorded in `token_report`.
- With the example profile, `model` is `CONFIGURED_LATER`, so `gpt_local_default` is a local source input token estimate using fallback encoding, not a final billing token count.

Gemini-family:

- Uses `GeminiSentencePieceApproxCounter`.
- If a SentencePiece model path is supplied and usable, counts local pieces.
- If no model is supplied, uses a local heuristic fallback.
- It is explicitly approximate and is not an official Gemini billing count.
- The heuristic estimate is useful for corpus scale planning only and should not be used directly for cost comparison.

No provider `countTokens` API is called.

## 11. token_report Shape

`token_report` includes:

- `source_path`
- `source_commit`
- `literature_id`
- `text_layer`
- `total_segments`
- `total_source_chars`
- `total_normalized_chars`
- `tokenizers_used`
- `tokenizer_warnings`
- `estimated_source_tokens_by_profile`
- `average_tokens_per_segment_by_profile`
- `p50_p90_p95_segment_tokens_by_profile`
- `top_20_largest_segments_by_profile`
- `segments_over_token_threshold_by_profile`
- `chunk_type_token_breakdown`
- `heading_token_breakdown`
- `text_layer_token_breakdown`

These values are source input token estimates from `original_text`/`normalized_text`. Real translation cost cannot be calculated from source tokens alone. The later cost-analysis phase must add `prompt_overhead_tokens`, `context_overhead_tokens`, and `estimated_output_tokens`, then apply official provider pricing in a separate volatile cost profile.

## 12. Corpus Token Summary Design

Implemented:

- `backend/pali/scripts/count_vri_corpus_tokens.py`

Example:

```bash
python3 backend/pali/scripts/count_vri_corpus_tokens.py \
  --input-dir data/tipitaka-xml/romn \
  --include-layers mul,att,tik \
  --token-profiles config/pali_token_profiles.example.json \
  --out /tmp/vri_romn_corpus_token_summary.json \
  --pretty
```

Corpus summary includes:

- `input_dir`
- `source_commit`
- `included_layers`
- `excluded_layers`
- `total_files`
- `files_by_text_layer`
- `segments_by_text_layer`
- `chars_by_text_layer`
- `tokens_by_text_layer_and_profile`
- `tokens_by_pitaka_and_profile`
- `tokens_by_nikaya_and_profile`
- `largest_files_by_tokens`
- `largest_segments_by_tokens`
- `files_with_errors`
- `files_with_warnings`
- `unknown_filename_patterns`
- `import_report_totals`
- `tokenizer_fallbacks_used`
- `tokenizer_warnings`
- `generated_at`

Target rollups:

- Pali mula/root text total GPT estimated tokens.
- Pali atthakatha/commentary total GPT estimated tokens.
- Pali tika/subcommentary total GPT estimated tokens.
- Pali mula/root text total Gemini approximate tokens.
- Pali atthakatha/commentary total Gemini approximate tokens.
- Pali tika/subcommentary total Gemini approximate tokens.

### 12.1 Token Terminology

Use the term `source input token estimate` for current reports. Do not describe these counts as total translation tokens or final cost basis.

Current summary numbers exclude:

- system/developer/user prompt overhead
- XML/source metadata included in prompts
- grammar-analysis instructions
- DPD or dictionary hints
- context carried across segments
- output translation tokens
- reviewer/commentary output tokens

## 13. Gemini countTokens Calibration Design

Do not call Gemini `countTokens` across the full corpus in this phase.

Next-step sample-only calibration design:

1. Stratify segments by `text_layer`: `mula`, `atthakatha`, `tika`.
2. Within each layer, sample short, medium, and long segments by local token estimate.
3. Use 100-300 total samples, preserving `stable_segment_key`, `source_path`, `chunk_type`, and local estimates.
4. Call Gemini official `countTokens` only for those samples.
5. Compare official sample counts against `gemini_local_approx`.
6. Compute ratios by layer, chunk type, and length bucket.
7. Apply those ratios as calibration coefficients to corpus-level estimates.
8. Keep raw official sample counts and calibration coefficients versioned separately from Segment JSON.

## 14. Explicitly Out of Scope

- LLM translation execution.
- Gemini/OpenAI/Claude text generation API calls.
- Official provider `countTokens` API calls.
- Official price-based total cost or detailed cost analysis.
- DB migration.
- RAG.
- Embedding.
- PDF diff.
- Legacy PDF segment alignment.

## 15. Remaining Uncertainties

- Exact canonical meaning and production inclusion policy for `.nrf.xml`.
- Full scholarly mapping from all VRI filenames to pitaka, nikaya, book, mūla/aṭṭhakathā/ṭīkā hierarchy.
- Whether `centre` should always be skipped or sometimes imported as a display/source segment.
- Whether notes should later become separate translatable apparatus segments.
- Whether verse grouping should remain verse-level or later support child line-level grammar analysis.
- Reconciliation policy when upstream XML structure changes but text remains mostly identical.
