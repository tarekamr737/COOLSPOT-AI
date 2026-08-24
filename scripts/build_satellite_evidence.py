"""Build the image-free normalized satellite surface-evidence artifact."""

import os

from api.app.services.satellite_evidence import (
    DEFAULT_SATELLITE_EVIDENCE_PATH,
    build_satellite_evidence,
    canonical_satellite_evidence_bytes,
)


def main() -> None:
    artifact = build_satellite_evidence()
    temporary = DEFAULT_SATELLITE_EVIDENCE_PATH.with_suffix(".json.part")
    temporary.write_bytes(canonical_satellite_evidence_bytes(artifact))
    os.replace(temporary, DEFAULT_SATELLITE_EVIDENCE_PATH)
    print(f"wrote satellite evidence for {artifact.site_count} pavement finalist")


if __name__ == "__main__":
    main()
