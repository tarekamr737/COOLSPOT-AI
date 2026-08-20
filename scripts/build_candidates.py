"""Build or verify the deterministic Pacoima intervention candidates."""

from __future__ import annotations

import argparse
import os

from api.app.services.candidates import (
    DEFAULT_CANDIDATES_PATH,
    build_candidates,
    canonical_candidate_bytes,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = canonical_candidate_bytes(build_candidates())
    if args.check:
        if not DEFAULT_CANDIDATES_PATH.exists():
            raise SystemExit("candidate artifact is missing")
        if DEFAULT_CANDIDATES_PATH.read_bytes() != payload:
            raise SystemExit("candidate artifact is not reproducible from committed inputs")
        print("Candidate artifact matches committed inputs byte-for-byte")
        return
    DEFAULT_CANDIDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = DEFAULT_CANDIDATES_PATH.with_suffix(
        f"{DEFAULT_CANDIDATES_PATH.suffix}.part"
    )
    temporary_path.write_bytes(payload)
    os.replace(temporary_path, DEFAULT_CANDIDATES_PATH)
    print(f"Wrote {DEFAULT_CANDIDATES_PATH} ({len(payload)} bytes)")


if __name__ == "__main__":
    main()
