"""Download and validate the authoritative public-data cache."""

import argparse
import json
from datetime import date
from pathlib import Path

from api.app.services.public_data import cache_public_sources, load_sources


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrieved-at", required=True, type=date.fromisoformat)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--sources", type=Path, default=Path("data/sources.json"))
    parser.add_argument("--manifest", type=Path, default=Path("data/raw_manifest.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workspace = Path.cwd().resolve()
    registry = load_sources(args.sources)
    manifest = cache_public_sources(
        registry,
        workspace,
        retrieved_at=args.retrieved_at,
        refresh=args.refresh,
    )
    args.manifest.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    for artifact in manifest.artifacts:
        print(
            f"{artifact.artifact_id}: {artifact.record_count} records, "
            f"{artifact.byte_count} bytes, sha256={artifact.sha256}"
        )


if __name__ == "__main__":
    main()
