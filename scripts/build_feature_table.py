"""Build or verify the deterministic Pacoima tile feature table."""

from __future__ import annotations

import argparse
import os

from api.app.services.feature_table import (
    DEFAULT_FEATURE_TABLE_PATH,
    build_feature_table,
    canonical_feature_table_bytes,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = canonical_feature_table_bytes(build_feature_table())
    if args.check:
        if not DEFAULT_FEATURE_TABLE_PATH.exists():
            raise SystemExit("feature table is missing")
        if DEFAULT_FEATURE_TABLE_PATH.read_bytes() != payload:
            raise SystemExit("feature table is not reproducible from committed inputs")
        print("Feature table matches committed inputs byte-for-byte")
        return
    DEFAULT_FEATURE_TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = DEFAULT_FEATURE_TABLE_PATH.with_suffix(
        f"{DEFAULT_FEATURE_TABLE_PATH.suffix}.part"
    )
    temporary_path.write_bytes(payload)
    os.replace(temporary_path, DEFAULT_FEATURE_TABLE_PATH)
    print(f"Wrote {DEFAULT_FEATURE_TABLE_PATH} ({len(payload)} bytes)")


if __name__ == "__main__":
    main()
