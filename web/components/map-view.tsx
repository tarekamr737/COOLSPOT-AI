"use client";

import { useEffect, useRef, useState } from "react";
import type {
  ExpressionSpecification,
  GeoJSONSource,
  Map as MapLibreMap,
  MapLayerMouseEvent,
} from "maplibre-gl";

import type {
  Candidate,
  Geometry,
  LayerName,
  LayerProperties,
  LayerResponse,
  Pilot,
} from "@/lib/api-schemas";

import styles from "./planning-shell.module.css";

type GeoJsonFeature = {
  type: "Feature";
  geometry: Geometry;
  properties: Record<string, string | number | boolean | null>;
};

type GeoJsonCollection = { type: "FeatureCollection"; features: GeoJsonFeature[] };

function scoreFor(properties: LayerProperties): number {
  switch (properties.layer) {
    case "heat":
      return properties.combined_heat_score;
    case "persistence":
      return properties.persistence_score;
    case "exposure":
      return properties.exposure_score;
    case "vulnerability":
      return properties.vulnerability_score;
  }
}

function layerCollection(layer: LayerResponse): GeoJsonCollection {
  return {
    type: "FeatureCollection",
    features: layer.features.map((feature) => ({
      type: "Feature",
      geometry: feature.geometry,
      properties: {
        layer: feature.properties.layer,
        tile_id: feature.properties.tile_id,
        display_score: scoreFor(feature.properties),
      },
    })),
  };
}

function geometryCenter(geometry: Geometry): [number, number] {
  if (geometry.type === "Point") return geometry.coordinates;
  const positions =
    geometry.type === "Polygon"
      ? geometry.coordinates.flat()
      : geometry.coordinates.flat(2);
  const total = positions.reduce(
    (sum, [longitude, latitude]) => [sum[0] + longitude, sum[1] + latitude],
    [0, 0],
  );
  return [total[0] / positions.length, total[1] / positions.length];
}

function candidateCollection(
  candidates: Candidate[],
  selectedCandidateIds: string[],
  activeCandidateId: string | null,
): GeoJsonCollection {
  const selected = new Set(selectedCandidateIds);
  return {
    type: "FeatureCollection",
    features: candidates
      .filter((candidate) => selected.has(candidate.id))
      .map((candidate) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: geometryCenter(candidate.geometry) },
        properties: {
          candidate_id: candidate.id,
          site_id: candidate.site_id,
          active: candidate.id === activeCandidateId,
        },
      })),
  };
}

function colorsFor(layer: LayerName): [string, string, string] {
  if (layer === "heat" || layer === "persistence") {
    return ["#fbbf24", "#f97316", "#991b1b"];
  }
  if (layer === "exposure") return ["#bdd7ff", "#4fdbc8", "#00796f"];
  return ["#ffd9dc", "#ff7b89", "#991b45"];
}

function layerFillExpression(layer: LayerName): ExpressionSpecification {
  const [low, middle, high] = colorsFor(layer);
  return ["interpolate", ["linear"], ["get", "display_score"], 0, low, 0.5, middle, 1, high];
}

type MapViewProps = {
  pilot: Pilot;
  layer: LayerResponse;
  candidates: Candidate[];
  selectedCandidateIds: string[];
  activeCandidateId: string | null;
  onSelectSite: (siteId: string) => void;
};

export function MapView({
  pilot,
  layer,
  candidates,
  selectedCandidateIds,
  activeCandidateId,
  onSelectSite,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const onSelectRef = useRef(onSelectSite);
  const latestPropsRef = useRef({
    pilot,
    layer,
    candidates,
    selectedCandidateIds,
    activeCandidateId,
  });
  const [mapState, setMapState] = useState<"loading" | "ready" | "unsupported">("loading");

  useEffect(() => {
    onSelectRef.current = onSelectSite;
  }, [onSelectSite]);

  useEffect(() => {
    latestPropsRef.current = { pilot, layer, candidates, selectedCandidateIds, activeCandidateId };
  }, [activeCandidateId, candidates, layer, pilot, selectedCandidateIds]);

  useEffect(() => {
    if (!containerRef.current || !("WebGLRenderingContext" in window)) {
      setMapState("unsupported");
      return;
    }

    let disposed = false;
    void import("maplibre-gl").then(({ Map, NavigationControl }) => {
      if (disposed || !containerRef.current) return;
      const initial = latestPropsRef.current;
      const map = new Map({
        container: containerRef.current,
        center: [-118.42, 34.27],
        zoom: 12.4,
        attributionControl: false,
        style: {
          version: 8,
          sources: {},
          layers: [{ id: "background", type: "background", paint: { "background-color": "#071a2b" } }],
        },
      });
      mapRef.current = map;
      map.addControl(new NavigationControl({ showCompass: false }), "top-right");
      map.on("load", () => {
        map.addSource("boundary", { type: "geojson", data: initial.pilot.boundary });
        map.addSource("analysis-layer", { type: "geojson", data: layerCollection(initial.layer) });
        map.addSource("portfolio-sites", {
          type: "geojson",
          data: candidateCollection(
            initial.candidates,
            initial.selectedCandidateIds,
            initial.activeCandidateId,
          ),
        });
        map.addLayer({
          id: "analysis-fill",
          type: "fill",
          source: "analysis-layer",
          paint: {
            "fill-color": layerFillExpression(initial.layer.layer) as never,
            "fill-opacity": 0.72,
          },
        });
        map.addLayer({
          id: "analysis-outline",
          type: "line",
          source: "analysis-layer",
          paint: { "line-color": "rgba(3, 20, 39, 0.42)", "line-width": 0.35 },
        });
        map.addLayer({
          id: "boundary-line",
          type: "line",
          source: "boundary",
          paint: { "line-color": "#d3e4fe", "line-width": 1.5, "line-opacity": 0.8 },
        });
        map.addLayer({
          id: "portfolio-sites",
          type: "circle",
          source: "portfolio-sites",
          paint: {
            "circle-radius": ["case", ["get", "active"], 8, 5],
            "circle-color": "#4fdbc8",
            "circle-stroke-color": "#031427",
            "circle-stroke-width": 2,
          },
        });
        const boundaryPositions = initial.pilot.boundary.features[0]?.geometry.coordinates[0];
        if (boundaryPositions?.length) {
          const longitudes = boundaryPositions.map(([longitude]) => longitude);
          const latitudes = boundaryPositions.map(([, latitude]) => latitude);
          map.fitBounds(
            [
              [Math.min(...longitudes), Math.min(...latitudes)],
              [Math.max(...longitudes), Math.max(...latitudes)],
            ],
            { padding: 42, duration: 0 },
          );
        }
        map.on("click", "portfolio-sites", (event: MapLayerMouseEvent) => {
          const siteId = event.features?.[0]?.properties?.site_id;
          if (typeof siteId === "string") onSelectRef.current(siteId);
        });
        map.on("mouseenter", "portfolio-sites", () => {
          map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", "portfolio-sites", () => {
          map.getCanvas().style.cursor = "";
        });
        setMapState("ready");
      });
    }).catch(() => {
      if (!disposed) setMapState("unsupported");
    });

    return () => {
      disposed = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.isStyleLoaded()) return;
    (map.getSource("analysis-layer") as GeoJSONSource | undefined)?.setData(
      layerCollection(layer) as never,
    );
    map.setPaintProperty("analysis-fill", "fill-color", layerFillExpression(layer.layer));
  }, [layer]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.isStyleLoaded()) return;
    (map.getSource("portfolio-sites") as GeoJSONSource | undefined)?.setData(
      candidateCollection(candidates, selectedCandidateIds, activeCandidateId) as never,
    );
  }, [activeCandidateId, candidates, selectedCandidateIds]);

  return (
    <div className={styles.mapVisual}>
      <div
        aria-label={`Interactive Pacoima ${layer.layer} layer map`}
        className={styles.mapContainer}
        ref={containerRef}
        role="region"
      />
      {mapState !== "ready" ? (
        <div className={styles.mapLoading} role="status">
          {mapState === "unsupported"
            ? "Map rendering is unavailable in this browser. Layer data remains available in the panels."
            : "Rendering cached Pacoima layer…"}
        </div>
      ) : null}
      <p className={styles.mapTruth}>Verified tiles and selected candidate locations. No basemap required.</p>
    </div>
  );
}
