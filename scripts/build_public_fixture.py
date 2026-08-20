"""Build or verify the committed Pacoima public-data fixture."""

import argparse
import hashlib
from pathlib import Path

from api.app.services.processed_data import build_public_fixture, canonical_fixture_bytes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/pacoima_public_data.json"),
    )
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workspace = args.workspace.resolve()
    output = args.output if args.output.is_absolute() else workspace / args.output
    document = build_public_fixture(workspace)
    payload = canonical_fixture_bytes(document)

    if args.check:
        if not output.exists() or output.read_bytes() != payload:
            raise SystemExit(f"Processed fixture is stale: {output}")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)

    digest = hashlib.sha256(payload).hexdigest()
    print(f"Validated {output}: sha256={digest}, counts={document.counts.model_dump()}")


if __name__ == "__main__":
    main()
