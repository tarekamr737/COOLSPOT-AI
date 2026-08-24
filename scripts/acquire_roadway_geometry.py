"""Acquire a complete official street-centerline snapshot for the Pacoima AOI."""

import os

from api.app.services.roadway_geometry import (
    DEFAULT_ROADWAY_PATH,
    acquire_street_centerlines,
    canonical_street_centerline_bytes,
)


def main() -> None:
    document = acquire_street_centerlines()
    DEFAULT_ROADWAY_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = DEFAULT_ROADWAY_PATH.with_suffix(".geojson.part")
    temporary.write_bytes(canonical_street_centerline_bytes(document))
    os.replace(temporary, DEFAULT_ROADWAY_PATH)
    print(f"acquired {len(document.features)} official street centerlines")


if __name__ == "__main__":
    main()
