from pathlib import Path

from backend.pali.importers.vri_xml import parse_source_file, parse_vri_xml
from backend.pali.scripts.count_vri_corpus_tokens import count_corpus_tokens
from backend.pali.tokenization.token_counter import build_token_report


SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<TEI.2>
  <teiHeader/>
  <text>
    <front/>
    <body xml:space="preserve">
      <p rend="nikaya">Khuddakanikāye</p>
      <div id="kn5" n="kn5" type="book">
        <head rend="book">Suttanipātapāḷi</head>
        <div id="kn5_1" n="kn5_1" type="vagga">
          <head rend="chapter">1. Uragavaggo</head>
          <p rend="subhead">1. Uragasuttaṃ</p>
          <p rend="bodytext" n="1"><pb ed="T" n="PAGE-1"/>Evaṃ me sutaṃ <note>VARIANT</note> ekaṃ samayaṃ.</p>
          <p rend="hangnum" n="2">2.</p>
          <p rend="gatha1">Yo uppatitaṃ vineti kodhaṃ,</p>
          <p rend="gathalast">urago jiṇṇamivattacaṃ purāṇaṃ.</p>
        </div>
      </div>
    </body>
  </text>
</TEI.2>
"""


def write_sample(path: Path, text: str = SAMPLE_XML) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_filename_layer_detection():
    assert parse_source_file("s0505m.mul.xml")["text_layer"] == "mula"
    assert parse_source_file("s0505a.att.xml")["text_layer"] == "atthakatha"
    assert parse_source_file("s0101t.tik.xml")["text_layer"] == "tika"
    assert parse_source_file("abh04t.nrf.xml")["text_layer"] == "nrf"
    assert parse_source_file("vin02a1.att.xml")["book_code"] == "vin02a1"


def test_segment_key_repeatability(tmp_path):
    xml_path = write_sample(tmp_path / "s0505m.mul.xml")
    first = parse_vri_xml(xml_path, source_path="romn/s0505m.mul.xml")
    second = parse_vri_xml(xml_path, source_path="romn/s0505m.mul.xml")
    assert [s["stable_segment_key"] for s in first["segments"]] == [
        s["stable_segment_key"] for s in second["segments"]
    ]


def test_source_text_hash_repeatability(tmp_path):
    xml_path = write_sample(tmp_path / "s0505m.mul.xml")
    first = parse_vri_xml(xml_path, source_path="romn/s0505m.mul.xml")
    second = parse_vri_xml(xml_path, source_path="romn/s0505m.mul.xml")
    assert [s["source_text_hash"] for s in first["segments"]] == [
        s["source_text_hash"] for s in second["segments"]
    ]


def test_page_break_not_in_original_text(tmp_path):
    xml_path = write_sample(tmp_path / "s0505m.mul.xml")
    artifact = parse_vri_xml(xml_path, source_path="romn/s0505m.mul.xml")
    first = artifact["segments"][0]
    assert "PAGE-1" not in first["original_text"]
    assert first["edition_ref"] == [{"ed": "T", "n": "PAGE-1"}]


def test_note_not_in_original_text(tmp_path):
    xml_path = write_sample(tmp_path / "s0505m.mul.xml")
    artifact = parse_vri_xml(xml_path, source_path="romn/s0505m.mul.xml")
    first = artifact["segments"][0]
    assert "VARIANT" not in first["original_text"]
    assert first["notes"] == ["VARIANT"]


def test_sort_order_unique(tmp_path):
    xml_path = write_sample(tmp_path / "s0505m.mul.xml")
    artifact = parse_vri_xml(xml_path, source_path="romn/s0505m.mul.xml")
    sort_orders = [segment["sort_order"] for segment in artifact["segments"]]
    assert sort_orders == [1, 2]
    assert artifact["import_report"]["sort_order_unique"] is True
    assert artifact["import_report"]["segment_count_by_chunk_type"] == {"prose": 1, "verse": 1}


def test_token_counter_returns_counts(tmp_path):
    xml_path = write_sample(tmp_path / "s0505m.mul.xml")
    artifact = parse_vri_xml(xml_path, source_path="romn/s0505m.mul.xml")
    report = build_token_report(
        artifact,
        profiles=[
            {
                "profile_id": "gemini_local_approx",
                "provider": "gemini",
                "counter": "sentencepiece_or_heuristic",
                "sentencepiece_model_path": None,
            }
        ],
    )
    assert report["estimated_source_tokens_by_profile"]["gemini_local_approx"] > 0
    assert report["tokenizers_used"]["gemini_local_approx"]["approximate"] is True


def test_corpus_summary_groups_by_text_layer(tmp_path):
    write_sample(tmp_path / "s0505m.mul.xml")
    write_sample(tmp_path / "s0505a.att.xml")
    summary = count_corpus_tokens(
        tmp_path,
        include_layers={"mula", "atthakatha"},
        token_profiles_path=None,
    )
    assert summary["files_by_text_layer"]["mula"] == 1
    assert summary["files_by_text_layer"]["atthakatha"] == 1
    assert summary["segments_by_text_layer"]["mula"] == 2
    assert summary["segments_by_text_layer"]["atthakatha"] == 2
