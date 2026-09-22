"""Content import and public API tests on disposable local PostgreSQL databases."""

import copy
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.pali.db.base import Base
from backend.pali.db.models import Literature, Segment
from backend.pali.db.publications import (
    CanonicalSource,
    LiteraturePublication,
    ReleasedTranslation,
    TranslationRelease,
)
from backend.pali.services.publication_import import (
    LITERATURE_ID,
    RELEASE_ID,
    Artifact,
    import_release,
    location,
    publish_release,
    validate_artifact,
)

ARTIFACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data/reports/pali/production_plan/dhammapada_v22_flash38_20260907/review/translations.json"
)


@pytest.fixture(scope="module")
def artifact():
    return validate_artifact(ARTIFACT_PATH)


@pytest.fixture
def database():
    target = os.environ.get("BUDDHA_TEST_POSTGRES_URL")
    if not target:
        pytest.skip("Set BUDDHA_TEST_POSTGRES_URL to the local PostgreSQL target")
    url = make_url(target)
    assert url.host in {"127.0.0.1", "localhost"} and url.port == 5434
    name = "buddhakorea_test_" + uuid4().hex
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    engine = create_engine(url.set(database=name))
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}"'))
        admin.dispose()


@pytest.fixture
def client(database):
    from backend.pali.api.v1 import literature, reading
    from backend.pali.db.database import get_db

    app = FastAPI()
    app.include_router(literature.router, prefix="/literature")
    app.include_router(reading.router, prefix="/literature")

    def test_db():
        with Session(database) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    with TestClient(app) as test_client:
        yield test_client


def load(database, artifact, publish=False, release=RELEASE_ID):
    with Session(database) as db, db.begin():
        result = import_release(db, artifact, release)
        if publish:
            publish_release(db, release)
        return result


def test_complete_artifact_and_duplicate_xml_heading(artifact):
    assert len(artifact.items) == 438
    assert sum(location(item["source"])[2] == "verse" for item in artifact.items) == 423
    ninth = next(
        item["source"] for item in artifact.items if item["source"]["canonical_ref"] == "kn2_2:116"
    )
    assert location(ninth) == (9, 116, "verse")
    supplement = next(
        item["source"]
        for item in artifact.items
        if item["source"]["canonical_ref"] == "kn2_24:seg-000360"
    )
    assert location(supplement) == (24, None, "supplement")


@pytest.mark.parametrize("corruption", ["duplicate", "hash", "failed", "schema"])
def test_invalid_artifact_rejected_before_database(tmp_path, corruption):
    data = json.loads(ARTIFACT_PATH.read_text())
    if corruption == "duplicate":
        data["items"][1] = data["items"][0]
    elif corruption == "hash":
        data["items"][0]["source"]["normalized_text"] += "changed"
    elif corruption == "failed":
        data["items"][0]["result"]["status"] = "failed"
    else:
        data["items"][0]["result"]["parsed_translation_json"]["natural_ko"] = ""
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        validate_artifact(path)


def test_import_is_lossless_and_idempotent(database, artifact):
    assert load(database, artifact)["status"] == "imported"
    assert load(database, artifact)["status"] == "unchanged"
    with Session(database) as db:
        assert db.query(Segment).count() == db.query(ReleasedTranslation).count() == 438
        for item in artifact.items:
            source = db.get(CanonicalSource, item["source"]["stable_segment_key"])
            assert source.source_metadata == item["source"]
            assert (
                db.get(Segment, source.segment_id).original_text == item["source"]["original_text"]
            )
            translation = db.get(ReleasedTranslation, (RELEASE_ID, source.stable_key))
            assert translation.payload == item["result"]["parsed_translation_json"]
        assert db.query(LiteraturePublication).count() == 0


def test_conflicting_release_and_transaction_rollback(database, artifact):
    load(database, artifact)
    changed = Artifact("f" * 64, artifact.summary, copy.deepcopy(artifact.items))
    with pytest.raises(ValueError, match="different artifact"):
        load(database, changed)
    changed.items[100]["source"]["source_text_hash"] = "a" * 64
    with pytest.raises(ValueError, match="identity has changed"):
        load(database, changed, release="test-v2")
    with Session(database) as db:
        assert db.query(TranslationRelease).count() == 1
        assert db.query(ReleasedTranslation).count() == 438


def test_unpublished_content_inaccessible_on_all_read_routes(database, artifact, client):
    load(database, artifact)
    with Session(database) as db:
        segment_id = db.query(Segment.id).first()[0]
    assert client.get("/literature").json()["total_count"] == 0
    key = artifact.items[0]["source"]["stable_segment_key"]
    for suffix in [
        "",
        "/segments",
        f"/segments/{segment_id}",
        "/hierarchy",
        "/search?q=mano",
        "/reading",
        "/reading/segments",
        f"/reading/detail?key={key}",
        f"/reading/locate?key={key}",
    ]:
        assert client.get(f"/literature/{LITERATURE_ID}{suffix}").status_code == 404, suffix


def test_public_reading_has_no_writes_and_preserves_all_locations(database, artifact, client):
    load(database, artifact, publish=True)
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(database, "before_cursor_execute", record)
    try:
        book = client.get(f"/literature/{LITERATURE_ID}/reading").json()
        assert len(book["chapters"]) == 27
        all_segments = []
        for chapter in book["chapters"]:
            response = client.get(
                f"/literature/{LITERATURE_ID}/reading/segments",
                params={"chapter": chapter["id"], "release": book["release"]},
            )
            assert response.status_code == 200
            all_segments.extend(response.json()["segments"])
        assert len(all_segments) == 438
        assert {item["verse"] for item in all_segments if item["verse"]} == set(range(1, 424))
        assert len({item["key"] for item in all_segments}) == 438
        for index in [0, 115, 358, 359, 423, 437]:
            key = artifact.items[index]["source"]["stable_segment_key"]
            detail = client.get(
                f"/literature/{LITERATURE_ID}/reading/detail", params={"key": key}
            ).json()
            assert (
                detail["translation"] == artifact.items[index]["result"]["parsed_translation_json"]
            )
            assert "source_metadata" not in detail and "model_output_raw" not in detail
            assert (
                client.get(
                    f"/literature/{LITERATURE_ID}/reading/locate", params={"key": key}
                ).status_code
                == 200
            )
        assert (
            client.get(f"/literature/{LITERATURE_ID}/reading/segments?chapter=27").status_code
            == 404
        )
        assert (
            client.get(f"/literature/{LITERATURE_ID}/reading/locate?key=missing").status_code == 404
        )
        assert all(s.lstrip().upper().startswith("SELECT") for s in statements)
    finally:
        event.remove(database, "before_cursor_execute", record)


def test_release_switch_and_source_reuse(database, artifact, client):
    load(database, artifact, publish=True)
    changed = Artifact("e" * 64, artifact.summary, copy.deepcopy(artifact.items))
    changed.items[0]["result"]["parsed_translation_json"]["natural_ko"] = "검증용 두 번째 번역"
    load(database, changed, release="test-v2")
    key = artifact.items[0]["source"]["stable_segment_key"]
    with Session(database) as db, db.begin():
        publish_release(db, "test-v2")
    assert (
        client.get(
            f"/literature/{LITERATURE_ID}/reading/segments", params={"release": RELEASE_ID}
        ).status_code
        == 409
    )
    detail = client.get(f"/literature/{LITERATURE_ID}/reading/detail", params={"key": key}).json()
    assert detail["translation"]["natural_ko"] == "검증용 두 번째 번역"
    with Session(database) as db, db.begin():
        assert db.query(Segment).count() == 438
        publish_release(db, RELEASE_ID)
    assert client.get(f"/literature/{LITERATURE_ID}/reading").json()["release"] == RELEASE_ID


def test_legacy_api_format_unchanged(database, client):
    with Session(database) as db, db.begin():
        db.add(Literature(id="legacy", name="기존 문헌", pali_name="Test", pitaka="sutta"))
        db.flush()
        db.add(
            Segment(
                literature_id="legacy",
                paragraph_id=1,
                original_text="original",
                translation={"sentences": []},
                is_translated=True,
            )
        )
    result = client.get("/literature/legacy/segments")
    assert result.status_code == 200
    assert result.json()["segments"][0]["translation"] == {"sentences": []}


def test_other_published_book_uses_own_metadata_and_paginates(database, artifact, client):
    """A non-Dhammapada ID, chapter 30, and >200 rows must remain readable."""
    book_id = "another-published-book"
    with Session(database) as db, db.begin():
        db.add(
            Literature(
                id=book_id,
                name="검증용 문헌",
                pali_name="Test text",
                pitaka="sutta",
                content_type="canonical",
                total_segments=201,
                translated_segments=201,
            )
        )
        db.flush()
        db.add(
            TranslationRelease(
                id="test-other-release",
                literature_id=book_id,
                artifact_hash="a" * 64,
                source_commit="b" * 40,
                model="test",
                prompt_version="natural_ko_v2_2",
                segment_count=201,
            )
        )
        db.flush()
        for index in range(201):
            segment = Segment(
                literature_id=book_id,
                paragraph_id=index + 1,
                original_text="test",
                vagga_id=30,
                vagga_name="다른 문헌의 목차",
                is_translated=True,
            )
            db.add(segment)
            db.flush()
            key = f"test-source-{index}"
            db.add(
                CanonicalSource(
                    stable_key=key,
                    literature_id=book_id,
                    segment_id=segment.id,
                    source_hash="c" * 64,
                    sort_order=index + 1,
                    chapter=30,
                    kind="verse",
                    verse=index + 1,
                    source_metadata={
                        "source_repo": "https://github.com/VipassanaTech/tipitaka-xml",
                        "source_path": "romn/another.mul.xml",
                    },
                )
            )
            db.flush()
            db.add(
                ReleasedTranslation(
                    release_id="test-other-release",
                    source_key=key,
                    source_hash="c" * 64,
                    payload=artifact.items[0]["result"]["parsed_translation_json"],
                )
            )
        db.add(LiteraturePublication(literature_id=book_id, release_id="test-other-release"))
    book = client.get(f"/literature/{book_id}/reading").json()
    assert book["title"] == "검증용 문헌"
    assert book["chapter_label"] == "장"
    assert book["verse_count"] == 201
    assert book["chapters"][0]["title"] == "다른 문헌의 목차"
    assert book["source_url"].endswith("/romn/another.mul.xml")
    endpoint = f"/literature/{book_id}/reading/segments"
    first = client.get(endpoint, params={"chapter": 30}).json()
    second = client.get(endpoint, params={"chapter": 30, "offset": 200}).json()
    assert len(first["segments"]) == 200 and first["has_more"]
    assert len(second["segments"]) == 1 and not second["has_more"]
    assert len({item["key"] for item in first["segments"] + second["segments"]}) == 201
    assert client.get(endpoint, params={"chapter": -1}).status_code == 422


def test_interactive_translation_blocked_before_provider_creation(database, artifact, monkeypatch):
    from backend.pali.api.deps import get_literature_service
    from backend.pali.api.v1 import translate
    from backend.pali.db.database import get_db
    from backend.pali.services.literature_service import LiteratureService

    load(database, artifact, publish=True)
    app = FastAPI()
    app.include_router(translate.router, prefix="/translate")

    def test_db():
        with Session(database) as db:
            yield db

    def service():
        with Session(database) as db:
            yield LiteratureService(db)

    def forbidden():
        raise AssertionError("Reader must never construct a model client")

    monkeypatch.setattr(translate, "get_gemini_client", forbidden)
    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[get_literature_service] = service
    with Session(database) as db:
        segment_id = db.query(Segment.id).first()[0]
    with TestClient(app) as client:
        for route in ["", "/sync", "/batch"]:
            payload = {"literature_id": LITERATURE_ID, "force": True}
            payload["segment_ids" if route == "/batch" else "segment_id"] = (
                [segment_id] if route == "/batch" else segment_id
            )
            assert client.post("/translate" + route, json=payload).status_code == 409


def test_generic_prose_package_publish_and_immutable_location(database, client, artifact, tmp_path):
    from backend.pali.services.publication_package import validate_package

    item = copy.deepcopy(artifact.items[0])
    item["source"].update(literature_id="example-prose", stable_segment_key="example:passage:1")
    item["result"]["stable_segment_key"] = "example:passage:1"
    item["location"] = {"chapter": 30, "verse": None, "kind": "passage"}
    data = {
        "schema_version": "published_translation_v1",
        "literature": {
            "id": "example-prose",
            "name": "산문 예제",
            "pali_name": "Example",
            "pitaka": "sutta",
            "display_metadata": {"description": "산문 문헌"},
        },
        "summary": dict(artifact.summary, count=1),
        "items": [item],
    }
    path = tmp_path / "package.json"
    path.write_text(json.dumps(data, ensure_ascii=False))
    package = validate_package(path)
    with Session(database) as db, db.begin():
        assert import_release(db, package, "prose-v1")["status"] == "imported"
        assert import_release(db, package, "prose-v1")["status"] == "unchanged"
        publish_release(db, "prose-v1")
    response = client.get("/literature/example-prose/reading/segments?chapter=30")
    assert response.status_code == 200
    assert response.json()["segments"][0]["kind"] == "passage"
    assert client.get("/literature/example-prose/reading").json()["verse_count"] == 0
    data["items"][0]["location"]["chapter"] = 31
    path.write_text(json.dumps(data))
    changed = validate_package(path)
    with pytest.raises(ValueError, match="identity has changed"):
        with Session(database) as db, db.begin():
            import_release(db, changed, "prose-v2")
    assert client.get("/literature/example-prose/reading").json()["release"] == "prose-v1"
    data["items"][0]["source"]["original_text"] += " tampered"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        validate_package(path)
