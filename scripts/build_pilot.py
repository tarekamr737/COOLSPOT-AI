"""Build the committed Pacoima AOI from a downloaded LA City GeoJSON response."""

import argparse
import json
from datetime import date
from pathlib import Path

from pydantic import AnyHttpUrl

from api.app.services.boundary import (
    BoundaryCollection,
    BoundaryFeature,
    BoundaryProperties,
    calculate_area_sq_mi,
    parse_source_boundary,
    validate_boundary_file,
)

SOURCE_DATASET = "City of Los Angeles Neighborhood Councils (Certified)"
SOURCE_DATASET_URL = AnyHttpUrl(
    "https://maps.lacity.org/lahub/rest/services/Boundaries/MapServer/18"
)
SOURCE_QUERY_URL = AnyHttpUrl(
    f"{SOURCE_DATASET_URL}/query?where=NAME%3D%27PACOIMA%20NC%27"
    "&outFields=OBJECTID%2CNAME%2CNC_ID&returnGeometry=true&outSR=4326&f=geojson"
)
LICENSE_URL = AnyHttpUrl("https://data.lacity.org/terms-of-use")
LICENSE_NOTES = (
    "City of Los Angeles public data provided as-is for informational use under the Los "
    "Angeles Open Data Portal Terms of Use; no dataset-specific license is stated."
)


def build_aoi(source_path: Path, output_path: Path, retrieved_at: date) -> float:
    """Validate one source feature and write the normalized, traceable AOI."""

    source = parse_source_boundary(source_path.read_text(encoding="utf-8"))
    source_feature = source.features[0]
    area_sq_mi = calculate_area_sq_mi(source_feature.geometry)

    document = BoundaryCollection(
        type="FeatureCollection",
        features=(
            BoundaryFeature(
                type="Feature",
                properties=BoundaryProperties(
                    name="Pacoima",
                    boundary_label="Official Certified Neighborhood Council boundary",
                    storage_crs="EPSG:4326",
                    area_sq_mi=round(area_sq_mi, 6),
                    source_dataset=SOURCE_DATASET,
                    source_dataset_url=SOURCE_DATASET_URL,
                    source_query_url=SOURCE_QUERY_URL,
                    source_feature_name=source_feature.properties.NAME,
                    source_object_id=source_feature.properties.OBJECTID,
                    source_nc_id=source_feature.properties.NC_ID,
                    retrieved_at=retrieved_at,
                    license_notes=LICENSE_NOTES,
                    license_url=LICENSE_URL,
                ),
                geometry=source_feature.geometry,
            ),
        ),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(document.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    return validate_boundary_file(output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/pacoima_aoi.geojson"),
    )
    parser.add_argument("--retrieved-at", required=True, type=date.fromisoformat)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    area_sq_mi = build_aoi(args.source, args.output, args.retrieved_at)
    print(f"Validated Pacoima AOI: {area_sq_mi:.6f} sq mi")


if __name__ == "__main__":
    main()
