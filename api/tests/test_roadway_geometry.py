"""Tests for complete, deterministic street-centerline acquisition."""

import json
import urllib.parse

from api.app.services.roadway_geometry import (
    DEFAULT_PAVEMENT_PATH,
    DEFAULT_ROADWAY_PATH,
    acquire_street_centerlines,
    canonical_pavement_condition_bytes,
    canonical_street_centerline_bytes,
    load_pavement_conditions,
    load_street_centerlines,
)


def _feature(object_id: int) -> dict[str, object]:
    return {
        "type": "Feature",
        "id": object_id,
        "geometry": {
            "type": "LineString",
            "coordinates": [[-118.4, 34.25], [-118.39, 34.26]],
        },
        "properties": {
            "AutoID": object_id,
            "OBJECTID": object_id,
            "ASSETID": object_id,
            "STNAME": "TEST",
            "STSFX": "ST",
            "SFXDIR": None,
            "STATUS": "A",
            "ST_SUBTYPE": 1,
            "LST_MODF_DT": None,
            "BSS_ST_CLASS": "LOC",
            "Street_Designation": "Local Street",
            "Street_Designation_WO_Mod": "Local Street",
        },
    }


def test_acquisition_paginates_and_sorts_complete_response() -> None:
    def fetcher(url: str) -> bytes:
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        if query.get("returnCountOnly") == ["true"]:
            return b'{"count": 1001}'
        offset = int(query["resultOffset"][0])
        ids = range(1000, 0, -1) if offset == 0 else (1001,)
        payload = {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
            "features": [_feature(object_id) for object_id in ids],
            "exceededTransferLimit": offset == 0,
        }
        return json.dumps(payload).encode()

    document = acquire_street_centerlines(fetcher=fetcher)

    assert len(document.features) == 1001
    assert document.features[0].properties.AutoID == 1
    assert document.features[-1].properties.AutoID == 1001


def test_committed_street_centerlines_are_complete_and_canonical() -> None:
    document = load_street_centerlines()

    assert len(document.features) == 1913
    assert DEFAULT_ROADWAY_PATH.read_bytes() == canonical_street_centerline_bytes(document)


def test_committed_pavement_conditions_are_complete_and_canonical() -> None:
    document = load_pavement_conditions()

    assert len(document.features) == 1703
    assert {feature.properties.PCI_Category for feature in document.features} == {
        "Good",
        "Fair",
        "Poor",
    }
    assert all(feature.properties.Surface for feature in document.features)
    assert DEFAULT_PAVEMENT_PATH.read_bytes() == canonical_pavement_condition_bytes(document)
