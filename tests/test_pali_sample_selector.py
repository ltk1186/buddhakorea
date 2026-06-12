from pathlib import Path

from backend.pali.scripts.select_vri_translation_samples import select_vri_translation_samples


def make_xml(title: str, prose_repeat: int = 1) -> str:
    prose = " ".join(["Evaṃ me sutaṃ."] * prose_repeat)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<TEI.2>
  <text>
    <body>
      <p rend="nikaya">Khuddakanikāye</p>
      <p rend="book">{title}</p>
      <p rend="chapter">1. Testavaggo</p>
      <p rend="subhead">1. Testasuttaṃ</p>
      <p rend="bodytext" n="1">{prose}</p>
      <p rend="hangnum" n="2">2.</p>
      <p rend="gatha1">Dhammo have rakkhati dhammacāriṃ.</p>
      <p rend="gathalast">Dhammo suciṇṇo sukhamāvahāti.</p>
      <p rend="bodytext" n="3">{prose} {prose}</p>
    </body>
  </text>
</TEI.2>
"""


def test_select_vri_translation_samples(tmp_path: Path):
    (tmp_path / "s0505m.mul.xml").write_text(make_xml("Mula", 1), encoding="utf-8")
    (tmp_path / "s0505a.att.xml").write_text(make_xml("Atthakatha", 3), encoding="utf-8")
    (tmp_path / "s0519t.tik.xml").write_text(make_xml("Tika", 5), encoding="utf-8")

    result = select_vri_translation_samples(
        tmp_path,
        include_layers={"mula", "atthakatha", "tika"},
        source_commit="test-sha",
        calibration_size=6,
        pilot_size=5,
        seed=1,
    )

    assert result["source_commit"] == "test-sha"
    assert result["candidate_pool_report"]["segments_by_text_layer"] == {
        "atthakatha": 3,
        "mula": 3,
        "tika": 3,
    }
    assert len(result["calibration_samples"]) == 6
    assert len(result["pilot_samples"]) == 5
    assert {item["text_layer"] for item in result["calibration_samples"]} >= {
        "mula",
        "atthakatha",
        "tika",
    }
    assert {item["chunk_type"] for item in result["calibration_samples"]} >= {
        "prose",
        "verse",
    }
    assert {item["chunk_type"] for item in result["pilot_samples"]} >= {
        "prose",
        "verse",
    }
    assert all("token_estimates_by_profile" in item for item in result["pilot_samples"])
