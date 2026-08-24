"""Build the deterministic normalized environmental evidence artifact."""

from api.app.services.environmental_evidence import (
    DEFAULT_ENVIRONMENTAL_EVIDENCE_PATH,
    build_environmental_evidence,
    canonical_environmental_evidence_bytes,
)


def main() -> None:
    artifact = build_environmental_evidence()
    DEFAULT_ENVIRONMENTAL_EVIDENCE_PATH.write_bytes(
        canonical_environmental_evidence_bytes(artifact)
    )
    print(
        f"Wrote {len(artifact.sites)} finalist records to "
        f"{DEFAULT_ENVIRONMENTAL_EVIDENCE_PATH}"
    )


if __name__ == "__main__":
    main()
