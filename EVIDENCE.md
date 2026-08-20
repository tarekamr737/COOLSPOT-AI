# EVIDENCE

## Pacoima AOI is below the FortyGuard limit

- Requirement: committed Pacoima AOI is valid WGS84 GeoJSON and smaller than 10 mi².
- Artifact: `data/processed/pacoima_aoi.geojson`.
- Source: City of Los Angeles, `Neighborhood Councils (Certified)`, feature `PACOIMA NC`
  (`OBJECTID=64`, `NC_ID=7`), retrieved 2026-08-20.
- Method: Shapely geometry validation followed by area calculation in UTM zone 11N
  (`EPSG:32611`).
- Result: **7.763214 mi²**, below the 10 mi² hard limit and 9.5 mi² preferred ceiling.
- Test proof: `.venv\Scripts\python.exe -m pytest api/tests/test_boundary.py` → `3 passed`.
- Artifact SHA-256: `D166687F16077F8FA896B8B65BAD28F985A7243361B97F3DA8F4F6C59135D2E1`.
