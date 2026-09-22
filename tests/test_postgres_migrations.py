"""Real PostgreSQL tests. Run via `make dev-db-test`, never against production.

The runner creates uniquely named databases in the local Compose network and
only drops databases it created. Production fixture contains schema only.
"""

import asyncio
import os
import subprocess
import sys
import unittest
from pathlib import Path
from uuid import uuid4

import asyncpg

IN_MIGRATION_CONTAINER = Path("/app/backend/alembic.ini").exists()
FIXTURE = Path(__file__).parent / "fixtures/postgres/production_010_schema.sql"
EXPECTED_TABLES = {
    "alembic_version",
    "users",
    "chat_sessions",
    "chat_messages",
    "social_accounts",
    "user_usage",
    "anonymous_usage",
    "revoked_tokens",
    "saved_exchanges",
    "admin_audit_logs",
    "admin_query_reviews",
    "literatures",
    "segments",
    "query_logs",
    "canonical_sources",
    "translation_releases",
    "released_translations",
    "literature_publications",
}


async def query(database, sql, *args):
    connection = await asyncpg.connect(
        host="postgres",
        user="postgres",
        password="postgres",
        database=database,
    )
    try:
        return await connection.fetch(sql, *args)
    finally:
        await connection.close()


async def execute(database, sql):
    connection = await asyncpg.connect(
        host="postgres",
        user="postgres",
        password="postgres",
        database=database,
    )
    try:
        await connection.execute(sql)
    finally:
        await connection.close()


@unittest.skipUnless(IN_MIGRATION_CONTAINER, "Use make dev-db-test (isolated PostgreSQL)")
class PostgresMigrationTests(unittest.TestCase):
    def setUp(self):
        # Reject accidental invocation in a production migration container.
        self.assertEqual(os.environ.get("BUDDHA_MIGRATION_TEST"), "local-only")
        self.database = "buddhakorea_test_" + uuid4().hex
        asyncio.run(execute("postgres", f'CREATE DATABASE "{self.database}"'))
        self.addCleanup(
            lambda: asyncio.run(execute("postgres", f'DROP DATABASE "{self.database}"'))
        )

    def sql(self, sql):
        asyncio.run(execute(self.database, sql))

    def rows(self, sql):
        return asyncio.run(query(self.database, sql))

    def migrate(self, *args, succeeds=True):
        env = dict(os.environ)
        env["DATABASE_URL"] = (
            f"postgresql+asyncpg://postgres:postgres@postgres:5432/{self.database}"
        )
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
            cwd="/app/backend",
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        if succeeds:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def load_production_schema(self):
        self.sql(FIXTURE.read_text())
        self.migrate("stamp", "010")

    def seed_content(self):
        self.sql("""
            INSERT INTO users (id, nickname) VALUES (1, '테스트 계정');
            INSERT INTO saved_exchanges (user_id, question, answer)
                VALUES (1, '테스트 질문', '보존할 답변');
            INSERT INTO literatures (id, name, pali_name, pitaka, display_metadata)
                VALUES ('test-book', '검증용 경전', 'Dhammapada', 'sutta', '{"abbr":"검증"}');
            INSERT INTO segments (literature_id, paragraph_id, original_text, translation)
                VALUES ('test-book', 1, 'Manopubbaṅgamā', '{"sentences":[{"free_translation":"보존할 번역"}]}');
        """)

    def assert_content_preserved(self):
        self.assertEqual(
            self.rows(
                "SELECT translation->'sentences'->0->>'free_translation' AS value FROM segments"
            )[0]["value"],
            "보존할 번역",
        )
        self.assertEqual(
            self.rows("SELECT answer FROM saved_exchanges")[0]["answer"], "보존할 답변"
        )
        self.assertEqual(self.rows("SELECT count(*) AS n FROM segments")[0]["n"], 1)

    def assert_head(self):
        self.assertEqual(
            self.rows("SELECT version_num FROM alembic_version")[0]["version_num"], "014"
        )
        tables = {
            row["table_name"]
            for row in self.rows(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
            )
        }
        self.assertEqual(tables, EXPECTED_TABLES)

    def test_empty_database_and_repeat_upgrade(self):
        self.migrate("upgrade", "head")
        self.assert_head()
        self.seed_content()
        self.migrate("upgrade", "head")
        self.assert_content_preserved()
        self.sql("DELETE FROM literatures WHERE id='test-book'")
        self.assertEqual(self.rows("SELECT count(*) AS n FROM segments")[0]["n"], 0)

    def test_orm_metadata_import_needs_no_pali_runtime_settings(self):
        code = """
import sys
from sqlalchemy.orm import configure_mappers
from app.database import Base
from app.models import user, chat, social_account, user_usage, admin_audit_log, admin_query_review
from app.models.revoked_token import RevokedToken
from pali.db.base import Base as PaliBase
from pali.db import models
configure_mappers()
assert 'pali.config' not in sys.modules
assert {'literatures', 'segments', 'query_logs', 'canonical_sources', 'translation_releases', 'released_translations', 'literature_publications'} == set(PaliBase.metadata.tables)
assert {'saved_exchanges', 'revoked_tokens', 'anonymous_usage'} <= set(Base.metadata.tables)
record = RevokedToken(revocation_metadata={'test': True})
assert record.revocation_metadata == {'test': True}
assert RevokedToken.__table__.c.metadata.name == 'metadata'
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd="/app/backend",
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_010_preserves_existing_content(self):
        self.load_production_schema()
        self.seed_content()
        before = self.rows("""
            SELECT table_name, column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name IN ('literatures', 'segments', 'query_logs') AND column_name != 'content_type'
            ORDER BY table_name, ordinal_position
        """)
        self.migrate("upgrade", "head")
        self.migrate("upgrade", "head")
        self.assert_head()
        self.assert_content_preserved()
        after = self.rows("""
            SELECT table_name, column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name IN ('literatures', 'segments', 'query_logs') AND column_name != 'content_type'
            ORDER BY table_name, ordinal_position
        """)
        self.assertEqual(before, after)

    def test_older_pali_schema_gets_missing_optional_columns(self):
        self.load_production_schema()
        self.seed_content()
        self.sql(
            "ALTER TABLE literatures DROP COLUMN display_metadata; ALTER TABLE segments DROP COLUMN page_number;"
        )
        self.migrate("upgrade", "head")
        self.assert_content_preserved()
        self.assertEqual(
            self.rows("SELECT display_metadata FROM literatures")[0]["display_metadata"], "{}"
        )
        self.assertIsNone(self.rows("SELECT page_number FROM segments")[0]["page_number"])

    def test_unexpected_schema_fails_without_partial_ddl(self):
        self.load_production_schema()
        self.sql("ALTER TABLE segments DROP COLUMN original_text")
        result = self.migrate("upgrade", "head", succeeds=False)
        self.assertIn("Unexpected legacy schema", result.stderr)
        self.assertEqual(
            self.rows("SELECT version_num FROM alembic_version")[0]["version_num"], "010"
        )
        self.assertIsNone(self.rows("SELECT to_regclass('revoked_tokens') AS name")[0]["name"])
        self.assertIsNone(
            self.rows("SELECT to_regclass('ix_chat_messages_role_created_at') AS name")[0]["name"]
        )

    def test_003_repairs_old_baseline_and_keeps_002_columns(self):
        self.migrate("upgrade", "002")
        self.sql("ALTER TABLE chat_messages DROP COLUMN latency_ms")
        self.migrate("upgrade", "003")
        self.migrate("downgrade", "002")
        columns = {
            r["column_name"]
            for r in self.rows(
                "SELECT column_name FROM information_schema.columns WHERE table_name='chat_messages'"
            )
        }
        self.assertTrue({"latency_ms", "tokens_used", "sources_json"} <= columns)
        self.migrate("upgrade", "head")
        self.assert_head()

    def test_adopted_tables_cannot_be_dropped_by_downgrade(self):
        self.load_production_schema()
        self.seed_content()
        self.migrate("upgrade", "012")
        result = self.migrate("downgrade", "011", succeeds=False)
        self.assertIn("adopts existing data tables", result.stderr)
        self.assertEqual(
            self.rows("SELECT version_num FROM alembic_version")[0]["version_num"], "012"
        )
        self.assert_content_preserved()


if __name__ == "__main__":
    unittest.main(verbosity=2)
