"""Import an approved artifact into a local DB without translation API calls."""

import argparse
import json
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from ..services.publication_import import (
    RELEASE_ID,
    import_release,
    publish_release,
    validate_artifact,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "import", "publish"])
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--release", default=RELEASE_ID)
    args = parser.parse_args()
    artifact = None
    if args.command != "publish":
        if not args.artifact:
            parser.error("--artifact is required")
        artifact = validate_artifact(args.artifact)
    if args.command == "validate":
        print(
            json.dumps(
                {
                    "status": "valid",
                    "count": 438,
                    "body_verses": 423,
                    "artifact_hash": artifact.digest,
                }
            )
        )
        return
    url = make_url(os.environ.get("PALI_DATABASE_URL", ""))
    if url.host not in {"localhost", "127.0.0.1"} or url.database != "buddhakorea":
        parser.error(
            "This local preview command requires an explicit loopback PALI_DATABASE_URL for buddhakorea"
        )
    engine = create_engine(url)
    with Session(engine) as db, db.begin():
        result = (
            import_release(db, artifact, args.release)
            if args.command == "import"
            else publish_release(db, args.release)
        )
    engine.dispose()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
