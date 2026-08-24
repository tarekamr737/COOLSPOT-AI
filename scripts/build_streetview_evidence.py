"""Build the canonical image-free Street View evidence artifact."""

from __future__ import annotations

import os

from api.app.services.streetview_evidence import (
    DEFAULT_STREETVIEW_EVIDENCE_PATH,
    build_street_view_evidence_artifact,
    canonical_street_view_evidence_bytes,
)


def main() -> None:
    """Rebuild the processed artifact atomically from committed caches."""

    artifact = build_street_view_evidence_artifact()
    output_path = DEFAULT_STREETVIEW_EVIDENCE_PATH
    temporary = output_path.with_suffix(".json.part")
    temporary.write_bytes(canonical_street_view_evidence_bytes(artifact))
    os.replace(temporary, output_path)
    print(f"Wrote {artifact.site_count} sites to {output_path}")


if __name__ == "__main__":
    main()
