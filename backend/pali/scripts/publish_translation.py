"""Validate/import/publish completed translations locally or on the production host.

No model clients. All writes are explicit, hash-pinned and transactional.
"""

import argparse
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from ..db.publications import LiteraturePublication, TranslationRelease
from ..services.publication_import import import_release, publish_release, validate_artifact
from ..services.publication_package import validate_package


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "import", "publish", "unpublish", "status"])
    parser.add_argument("--artifact", type=Path)
    parser.add_argument(
        "--format", choices=["dhammapada", "publication-v1"], default="publication-v1"
    )
    parser.add_argument("--release", required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--target", choices=["local", "production"], default="local")
    args = parser.parse_args()
    artifact = None
    if args.command in {"validate", "import"}:
        if not args.artifact:
            parser.error("--artifact is required")
        artifact = (validate_artifact if args.format == "dhammapada" else validate_package)(
            args.artifact
        )
        if args.expected_sha256 and artifact.digest != args.expected_sha256:
            parser.error("Artifact SHA-256 differs from approved input")
        if args.command == "validate":
            print(
                json.dumps(
                    {
                        "status": "valid",
                        "count": len(artifact.items),
                        "artifact_hash": artifact.digest,
                    }
                )
            )
            return
    if args.command != "status" and not args.expected_sha256:
        parser.error("Writes require --expected-sha256 from the reviewed artifact")
    url = make_url(os.environ.get("PALI_DATABASE_URL", ""))
    hosts = {"127.0.0.1", "localhost"} if args.target == "local" else {"postgres"}
    if (
        url.host not in hosts
        or url.database != "buddhakorea"
        or url.get_backend_name() != "postgresql"
    ):
        parser.error("Target does not match the explicit local/production PostgreSQL connection")
    engine = create_engine(url)
    try:
        with Session(engine) as db, db.begin():
            if args.command == "import":
                result = import_release(db, artifact, args.release)
            else:
                release = db.get(TranslationRelease, args.release)
                if not release:
                    raise ValueError("Release not found")
                if args.expected_sha256 and release.artifact_hash != args.expected_sha256:
                    raise ValueError("Stored release hash differs from approved input")
                db.execute(select(func.pg_advisory_xact_lock(func.hashtext(release.literature_id))))
                publication = db.get(LiteraturePublication, release.literature_id)
                if args.command == "publish":
                    result = publish_release(db, args.release)
                elif args.command == "unpublish":
                    if publication and publication.release_id != args.release:
                        raise ValueError("Another release is public; refusing to unpublish it")
                    if publication:
                        db.delete(publication)
                    result = {"status": "unpublished", "release_id": args.release}
                else:
                    result = {
                        "release_id": release.id,
                        "literature_id": release.literature_id,
                        "artifact_hash": release.artifact_hash,
                        "count": release.segment_count,
                        "published": bool(publication and publication.release_id == release.id),
                    }
    finally:
        engine.dispose()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
