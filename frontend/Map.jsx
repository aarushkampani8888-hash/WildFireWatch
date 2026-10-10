import React, { useEffect, useMemo, useRef, useState } from "react";

import "maplibre-gl/dist/maplibre-gl.css";
import terrainWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import "mapbox-gl/dist/mapbox-gl.css";
import { nodes, edges } from "./simulation";
import { buildFireScenario } from "./fireScenario";
const xy = (p) => [42 + p[0] * 52, 32 + p[1] * 44];
export function ScenarioMap({ incident }) {
  const excluded = new Set(incident?.route.excluded.map((e) => e.edge) || []);
  return (
    <svg
      viewBox="0 0 720 620"
      role="img"
      aria-label="Synthetic road network with illustrative fire envelopes and candidate corridor"
    >
      {Array.from({ length: 13 }, (_, i) => (
        <g key={i}>
          <path
            d={`M${42 + i * 52} 32V560 M42 ${32 + i * 44}H666`}
            stroke="#293d2d"
            strokeWidth=".7"
          />
        </g>
      ))}
      <text x="55" y="58" fill="#829881" fontSize="10" letterSpacing="2">
        SYNTHETIC SECTOR / 12 × 12 KM
      </text>
      {edges.map(([a, b]) => (
        <line
          key={a + b}
          x1={xy(nodes[a])[0]}
          y1={xy(nodes[a])[1]}
          x2={xy(nodes[b])[0]}
          y2={xy(nodes[b])[1]}
          stroke={excluded.has(a + "-" + b) ? "#ae7768" : "#516451"}
          strokeWidth="5"
          strokeDasharray={excluded.has(a + "-" + b) ? "6 5" : ""}
        />
      ))}
      {[...(incident?.projections || [])].reverse().map((p) => (
        <polygon
          key={p.minutes}
          points={p.points.map((pt) => xy(pt).join(",")).join(" ")}
          fill="#e69456"
          fillOpacity={p.minutes === incident.horizon ? 0.18 : 0.035}
          stroke={p.minutes === incident.horizon ? "#efa96b" : "#755538"}
          strokeWidth={p.minutes === incident.horizon ? 2 : 1}
          strokeDasharray={p.minutes === incident.horizon ? "" : "5 7"}
        />
      ))}
      {incident?.route.path.length > 0 && !incident.route.geometry && (
        <polyline
          points={incident.route.path
            .map((n) => xy(nodes[n]).join(","))
            .join(" ")}
          fill="none"
          stroke="#d8ef8a"
          strokeWidth="5"
        />
      )}
      {Object.entries(nodes).map(([name, p]) => (
        <g key={name}>
          <circle
            cx={xy(p)[0]}
            cy={xy(p)[1]}
            r={name === "shelter" ? 9 : 6}
            fill={name === "shelter" ? "#d8ef8a" : "#17251b"}
            stroke="#adc699"
            strokeWidth="2"
          />
          <text
            x={xy(p)[0] + 12}
            y={xy(p)[1] - 12}
            fill="#bdd0b7"
            fontSize="11"
          >
            {name === "community"
              ? "Pine community"
              : name === "shelter"
                ? "Assembly point"
                : name}
          </text>
        </g>
      ))}
      <circle cx={xy([6, 5])[0]} cy={xy([6, 5])[1]} r="10" fill="#ee9d69" />
      <text
        x={xy([6, 5])[0] + 20}
        y={xy([6, 5])[1] + 5}
        fill="#f1b381"
        fontSize="11"
      >
        Assumed ignition
      </text>
      <text x="630" y="590" fill="#809680" fontSize="11">
        N ↑
      </text>
    </svg>
  );
}
const EMPTY = { type: "FeatureCollection", features: [] };
const HOME = { center: [-119.5, 37.4], zoom: 5.5, pitch: 0, bearing: 0 };
function decisionMarkerImage(kind) {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 64;
  const context = canvas.getContext("2d");
  context.beginPath();
  context.arc(32, 32, 28, 0, Math.PI * 2);
  context.fillStyle = kind === "confirmed_fire" ? "#c94032" : "#d98922";
  context.fill();
  context.lineWidth = 5;
  context.strokeStyle = "#fffdf6";
  context.stroke();
  if (kind === "confirmed_fire") {
    context.beginPath();
    context.moveTo(33, 12);
    context.bezierCurveTo(36, 21, 49, 24, 45, 39);
    context.bezierCurveTo(43, 49, 37, 54, 29, 52);
    context.bezierCurveTo(18, 50, 15, 41, 20, 33);
    context.bezierCurveTo(23, 28, 29, 24, 28, 17);
    context.bezierCurveTo(31, 20, 33, 23, 33, 27);
    context.bezierCurveTo(38, 22, 35, 17, 33, 12);
    context.closePath();
    context.fillStyle = "#fff8dc";
    context.fill();
  } else {
    context.beginPath();
    context.moveTo(32, 12);
    context.lineTo(53, 49);
    context.lineTo(11, 49);
    context.closePath();
    context.fillStyle = "#fff8dc";
    context.fill();
    context.strokeStyle = "#fff8dc";
    context.lineWidth = 2;
    context.stroke();
    context.fillStyle = "#9b5b0e";
    context.font = "bold 27px sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText("!", 32, 36);
  }
  return context.getImageData(0, 0, canvas.width, canvas.height);
}
const FHSZ_QUERY = "https://services8.arcgis.com/Xr1lDrwMv89PhjD9/ArcGIS/rest/services/FHSZALL_v25_1_vcp/FeatureServer/0/query";
const DROUGHT_QUERY = "https://gis.fema.gov/arcgis/rest/services/Partner/Drought_Current/FeatureServer/0/query";
function viewportQuery(url, bounds, fields) {
  const params = new URLSearchParams({
    where: "1=1",
    geometry: `${bounds.getWest()},${bounds.getSouth()},${bounds.getEast()},${bounds.getNorth()}`,
    geometryType: "esriGeometryEnvelope",
    spatialRel: "esriSpatialRelIntersects",
    inSR: "4326",
    outSR: "4326",
    outFields: fields,
    returnGeometry: "true",
    resultRecordCount: "1800",
    f: "geojson",
  });
  return `${url}?${params}`;
}
function showActionConfirmation(popup, content, { title, description, onConfirm }) {
  const previous = Array.from(content.childNodes);
  const heading = document.createElement("strong");
  heading.textContent = title;
  const detail = document.createElement("p");
  detail.textContent = description;
  const buttons = document.createElement("div");
  buttons.className = "thermal-popup-actions";
  const confirm = document.createElement("button");
  confirm.type = "button";
  confirm.className = "primary";
  confirm.textContent = "Confirm action";
  confirm.addEventListener("click", () => {
    onConfirm();
    popup.remove();
  }, { once: true });
  const back = document.createElement("button");
  back.type = "button";
  back.textContent = "Go back";
  back.addEventListener("click", () => content.replaceChildren(...previous), { once: true });
  buttons.append(confirm, back);
  content.replaceChildren(heading, detail, buttons);
}
export default function Map({
  incident,
  token,
  focus,
  onSelect,
  onThermalAction,
  onTerrainInspect,
  onMapPointAction,
  hasSelectedReport = false,
  inspectPoint,
  onCamera,
  satelliteDate,
  publicFires,
  confirmedFirePoint,
  fireAssessment,
  replayFocus,
}) {
  const cameraSelection = useRef(onCamera);
  cameraSelection.current = onCamera;
  const selection = useRef(onSelect);
  selection.current = onSelect;
  const terrainInspection = useRef(onTerrainInspect);
  terrainInspection.current = onTerrainInspect;
  const thermalAction = useRef(onThermalAction);
  thermalAction.current = onThermalAction;
  const mapPointAction = useRef(onMapPointAction);
  mapPointAction.current = onMapPointAction;
  const mapPointPopup = useRef(null);
  const reportAvailable = useRef(hasSelectedReport);
  reportAvailable.current = hasSelectedReport;
  const target = useRef(),
    map = useRef(),
    latest = useRef(incident),
    latestPublicFires = useRef(publicFires || EMPTY),
    scenarioForEdit = useRef(null),
    dragRing = useRef(null),
    dragHandle = useRef(null),
    suppressMapClick = useRef(false);
  const [fatal, setFatal] = useState(""),
    [warning, setWarning] = useState(""),
    [ready, setReady] = useState(false),
    [flat, setFlat] = useState(true),
    [terrainScale, setTerrainScale] = useState(1.5),
    [scenarioPace, setScenarioPace] = useState(0.6),
    [editedOuterRing, setEditedOuterRing] = useState(null),
    [dragPreviewRing, setDragPreviewRing] = useState(null),
    [pendingBoundary, setPendingBoundary] = useState(false),
    [hazardVisible, setHazardVisible] = useState(false),
    [droughtVisible, setDroughtVisible] = useState(false),
    [hazardStatus, setHazardStatus] = useState("Not loaded"),
    [droughtStatus, setDroughtStatus] = useState("Not loaded"),
    [viewportRevision, setViewportRevision] = useState(0);
  latest.current = incident;
  latestPublicFires.current = publicFires || EMPTY;
  useEffect(() => {
    let disposed = false,
      instance,
      observer;
    setFatal("");
    setWarning("");
    setReady(false);
    setFlat(true);
    async function initialize() {
      try {
        const library = token
          ? (await import("mapbox-gl")).default
          : await import("maplibre-gl");
        if (disposed) return;
        if (!token) library.setWorkerUrl(terrainWorkerUrl);
        const m = new library.Map({
          container: target.current,
          ...(token ? { accessToken: token } : {}),
          style: token
            ? "mapbox://styles/mapbox/outdoors-v12"
            : "https://tiles.openfreemap.org/styles/liberty",
          ...HOME,
          maxPitch: 80,
          attributionControl: true,
        });
        m.doubleClickZoom.disable();
        instance = m;
        map.current = m;
        m.addControl(
          new library.NavigationControl({ visualizePitch: true }),
          "top-right",
        );
        m.addControl(
          new library.ScaleControl({ unit: "metric" }),
          "bottom-left",
        );
        observer = new ResizeObserver(() => m.resize());
        observer.observe(target.current);
        m.on("error", (event) => {
          if (event.sourceId === "elevation")
            setWarning(
              "Elevation tiles unavailable. Map remains usable; terrain may be incomplete.",
            );
          else
            setWarning(
              "Some map data could not load. Check network access or your optional Mapbox token.",
            );
        });
        m.on("load", () => {
          if (disposed) return;
          if (!token) library.setWorkerUrl(terrainWorkerUrl);
          m.addSource(
            "elevation",
            token
              ? {
                  type: "raster-dem",
                  url: "mapbox://mapbox.mapbox-terrain-dem-v1",
                  tileSize: 512,
                  maxzoom: 14,
                }
              : {
                  type: "raster-dem",
                  tiles: [
                    "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png",
                  ],
                  encoding: "terrarium",
                  tileSize: 256,
                  maxzoom: 15,
                  attribution:
                    'Elevation: <a href="https://registry.opendata.aws/terrain-tiles/">Mapzen / AWS Terrain Tiles</a>',
                },
          );
          m.setTerrain({ source: "elevation", exaggeration: 1.5 });
          const firstSymbol = m
            .getStyle()
            .layers.find((layer) => layer.type === "symbol")?.id;
          m.addLayer(
            {
              id: "terrain-shading",
              type: "hillshade",
              source: "elevation",
              paint: { "hillshade-exaggeration": 0.35 },
            },
            firstSymbol,
          );
          m.addSource("incident", {
            type: "geojson",
            data: latest.current?.geojson || EMPTY,
          });
          m.addSource("public-fires", {
            type: "geojson",
            data: latestPublicFires.current,
          });
          m.addSource("inspection-point", { type: "geojson", data: EMPTY });
          m.addSource("fire-scenario", { type: "geojson", data: EMPTY });
          m.addSource("scenario-front", { type: "geojson", data: EMPTY });
          m.addSource("scenario-edit-handles", { type: "geojson", data: EMPTY });
          m.addSource("calfire-hazard", { type: "geojson", data: EMPTY });
          m.addSource("weekly-drought", { type: "geojson", data: EMPTY });
          m.addLayer({
            id: "weekly-drought-fill", type: "fill", source: "weekly-drought",
            paint: { "fill-color": ["match", ["get", "dm"], 0, "#fff2a8", 1, "#f6c65b", 2, "#e9934d", 3, "#c95d45", 4, "#8c3341", "#bd9b62"], "fill-opacity": 0.28 },
          });
          m.addLayer({
            id: "calfire-hazard-fill", type: "fill", source: "calfire-hazard",
            paint: { "fill-color": ["match", ["get", "FHSZ_Description"], "Very High", "#a83c34", "High", "#e47a3d", "Moderate", "#efbd62", "#778779"], "fill-opacity": 0.25 },
          });
          m.addLayer({
            id: "calfire-hazard-line", type: "line", source: "calfire-hazard",
            paint: { "line-color": ["match", ["get", "FHSZ_Description"], "Very High", "#922c2c", "High", "#c76136", "Moderate", "#ce9e4f", "#7c8d7f"], "line-width": 0.7, "line-opacity": 0.65 },
          });
          m.addLayer({
            id: "official-perimeters",
            type: "fill",
            source: "public-fires",
            filter: ["==", ["get", "kind"], "official-perimeter"],
            paint: { "fill-color": "#e65e3f", "fill-opacity": 0.18 },
          });
          m.addLayer({
            id: "official-perimeter-outline",
            type: "line",
            source: "public-fires",
            filter: ["==", ["get", "kind"], "official-perimeter"],
            paint: { "line-color": "#c73e2b", "line-width": 2.5, "line-dasharray": [2, 1.5] },
          });
          m.addLayer({
            id: "regional-thermal",
            type: "circle",
            source: "public-fires",
            filter: ["==", ["get", "kind"], "thermal-anomaly"],
            paint: {
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 4, 10, 9],
              "circle-color": "#ff7b24",
              "circle-stroke-color": "#fff4d6",
              "circle-stroke-width": 2,
              "circle-opacity": 0.94,
            },
          });
          m.addLayer({
            id: "inspection-point",
            type: "circle",
            source: "inspection-point",
            paint: {
              "circle-radius": 9,
              "circle-color": "#d8ef8a",
              "circle-stroke-color": "#163a2f",
              "circle-stroke-width": 3,
              "circle-opacity": 0.98,
            },
          });
          m.addLayer({
            id: "scenario-envelope",
            type: "fill",
            source: "fire-scenario",
            paint: {
              "fill-color": ["case", ["get", "adjusted"], "#35b96b", [
                "match", ["get", "minutes"],
                30, "#c92d24", 60, "#eb5033", "#ff9560",
              ]],
              "fill-opacity": [
                "match", ["get", "minutes"],
                30, 0.34, 60, 0.22, 0.12,
              ],
              "fill-antialias": true,
            },
          }, "inspection-point");
          m.addLayer({
            id: "scenario-edge",
            type: "line",
            source: "fire-scenario",
            paint: {
              "line-color": ["case", ["get", "adjusted"], "#26a956", [
                "match", ["get", "minutes"],
                30, "#a91f1a", 60, "#d93b2b", "#f58150",
              ]],
              "line-width": ["match", ["get", "minutes"], 30, 2.8, 60, 2, 1.4],
              "line-opacity": 0.88,
              "line-dasharray": [1.2, 0.8],
            },
            }, "inspection-point");
          m.addLayer({
            id: "scenario-front-fill",
            type: "fill",
            source: "scenario-front",
            paint: {
              "fill-color": "#ef3325",
              "fill-opacity": 0.3,
              "fill-antialias": true,
            },
          }, "inspection-point");
          m.addLayer({
            id: "scenario-front-glow",
            type: "line",
            source: "scenario-front",
            paint: {
              "line-color": "#ff3a27",
              "line-width": 11,
              "line-blur": 7,
              "line-opacity": 0.38,
            },
          }, "inspection-point");
          m.addLayer({
            id: "scenario-front-edge",
            type: "line",
            source: "scenario-front",
            paint: {
              "line-color": "#b91f1a",
              "line-width": 3,
              "line-opacity": 0.94,
            },
          }, "inspection-point");
          m.addLayer({
            id: "scenario-edit-handles",
            type: "circle",
            source: "scenario-edit-handles",
            paint: {
              "circle-radius": 6,
              "circle-color": "#38bf70",
              "circle-stroke-color": "#ffffff",
              "circle-stroke-width": 2,
            },
          });
          for (const layer of [
            {
              id: "perimeter",
              type: "fill",
              filter: ["==", ["get", "kind"], "perimeter"],
              paint: {
                "fill-color": "#f07838",
                "fill-opacity": ["case", ["get", "selected"], 0.3, 0.08],
              },
            },
            {
              id: "perimeter-outline",
              type: "line",
              filter: ["==", ["get", "kind"], "perimeter"],
              paint: {
                "line-color": "#ea762d",
                "line-width": ["case", ["get", "selected"], 3, 1],
              },
            },
            {
              id: "roads",
              type: "line",
              filter: ["==", ["get", "kind"], "road"],
              paint: {
                "line-color": [
                  "case",
                  ["get", "excluded"],
                  "#ba635c",
                  "#63705b",
                ],
                "line-width": 3,
                "line-opacity": 0.65,
              },
            },
            {
              id: "route-casing",
              type: "line",
              filter: ["==", ["get", "kind"], "route"],
              paint: { "line-color": "#183326", "line-width": 9 },
            },
            {
              id: "route",
              type: "line",
              filter: ["==", ["get", "kind"], "route"],
              paint: { "line-color": "#d8ef8a", "line-width": 5 },
            },
            {
              id: "report-matches",
              type: "line",
              filter: ["==", ["get", "kind"], "report-match"],
              paint: {
                "line-color": "#148d78",
                "line-width": 3,
                "line-dasharray": [2, 2],
                "line-opacity": 0.85,
              },
            },
            {
              id: "locations",
              type: "circle",
              filter: [
                "in",
                ["get", "kind"],
                [
                  "literal",
                  ["node", "ignition", "report", "hotspot", "camera"],
                ],
              ],
              paint: {
                "circle-color": [
                  "case",
                  ["==", ["get", "kind"], "ignition"],
                  "#f08542",
                  [
                    "case",
                    ["==", ["get", "kind"], "hotspot"],
                    "#ea743a",
                    "#42c5b3",
                  ],
                ],
                "circle-radius": 7,
                "circle-stroke-color": "#24392b",
                "circle-stroke-width": 2,
              },
            },
            {
              id: "labels",
              type: "symbol",
              filter: [
                "in",
                ["get", "kind"],
                ["literal", ["node", "report", "hotspot", "camera", "confirmed_fire", "escalated"]],
              ],
              layout: {
                "text-field": ["get", "name"],
                "text-size": 12,
                "text-offset": [0, 1.4],
                "text-anchor": "top",
              },
              paint: {
                "text-color": "#1c3021",
                "text-halo-color": "#f4f3df",
                "text-halo-width": 2,
              },
            },
          ])
            m.addLayer({ ...layer, source: "incident" });
          m.addImage("confirmed-fire-marker", decisionMarkerImage("confirmed_fire"), { pixelRatio: 2 });
          m.addImage("escalation-marker", decisionMarkerImage("escalated"), { pixelRatio: 2 });
          m.addLayer({
            id: "decision-markers",
            type: "symbol",
            source: "incident",
            filter: ["in", ["get", "kind"], ["literal", ["confirmed_fire", "escalated"]]],
            layout: {
              "icon-image": ["match", ["get", "kind"], "confirmed_fire", "confirmed-fire-marker", "escalation-marker"],
              "icon-size": 0.55,
              "icon-allow-overlap": true,
              "icon-ignore-placement": true,
              "icon-anchor": "center",
            },
          });
          m.on("click", "decision-markers", (event) => {
            const reportId = event.features?.[0]?.properties?.report_id;
            if (reportId) selection.current?.(reportId);
          });
          m.on("mouseenter", "decision-markers", () => { m.getCanvas().style.cursor = "pointer"; });
          m.on("mouseleave", "decision-markers", () => { m.getCanvas().style.cursor = ""; });
          m.on("click", "locations", (e) => {
            const feature = e.features?.[0];
            const coordinates = feature?.geometry?.coordinates;
            const properties = feature?.properties || {};
            if (properties.kind === "hotspot" && coordinates?.length >= 2) {
              const latitude = Number(coordinates[1]);
              const longitude = Number(coordinates[0]);
              const content = document.createElement("div");
              content.className = "thermal-popup";
              const heading = document.createElement("strong");
              const isDemo = properties.demo === true || properties.demo === "true";
              heading.textContent = isDemo ? "Staged thermal anomaly" : "Thermal anomaly";
              const description = document.createElement("p");
              description.textContent = `${properties.source || "Satellite source unavailable"} · ${properties.observed_at ? new Date(properties.observed_at).toLocaleString() : "observation time unavailable"}`;
              const coordinatesLabel = document.createElement("small");
              coordinatesLabel.textContent = `Pixel center · ${latitude.toFixed(5)}, ${longitude.toFixed(5)}${properties.satellite ? ` · ${properties.satellite}` : ""}${properties.confidence && properties.confidence !== "unknown" ? ` · confidence ${properties.confidence}` : ""}`;
              const caveat = document.createElement("small");
              caveat.className = "thermal-popup-caveat";
              caveat.textContent = "A heat pixel is not proof of wildfire and is not a fire perimeter.";
              const actions = document.createElement("div");
              actions.className = "thermal-popup-actions";
              const observation = { ...properties, latitude, longitude };
              for (const [label, action, style] of [
                ["Add to Evidence review + inbox", "add_to_review", ""],
                ["Mark for escalation", "escalated", ""],
                ["Confirm fire", "confirmed_fire", "primary"],
              ]) {
                const button = document.createElement("button");
                button.type = "button";
                button.className = style;
                button.textContent = label;
                if (isDemo && action !== "add_to_review") {
                button.disabled = true;
                button.title = "Staged anomalies are not real detections and cannot be confirmed or escalated.";
              }
              button.addEventListener("click", () => {
                const description = action === "confirmed_fire"
                  ? "This records your human confirmation for the thermal pixel. It does not contact authorities."
                  : action === "escalated"
                    ? "This marks the thermal pixel for escalation review. It does not notify an agency."
                    : "This adds the thermal pixel to Evidence review and the inbox for follow-up.";
                showActionConfirmation(popup, content, {
                  title: `Confirm: ${label}?`,
                  description: `${description} Coordinates: ${latitude.toFixed(5)}, ${longitude.toFixed(5)}.`,
                  onConfirm: () => thermalAction.current?.({ action, observation }),
                });
              }, { once: true });
                actions.append(button);
              }
              content.append(heading, description, coordinatesLabel, caveat, actions);
              const popup = new library.Popup({ closeButton: true, closeOnClick: true, maxWidth: "330px", offset: 14 })
                .setLngLat(coordinates)
                .setDOMContent(content)
                .addTo(m);
            e.preventDefault();
            return;
          }
            if (coordinates?.length >= 2)
              terrainInspection.current?.({ latitude: coordinates[1], longitude: coordinates[0] });
            const cameraId = properties.camera_id;
            if (cameraId) cameraSelection.current?.(cameraId);
            const id = properties.report_id;
            if (id) selection.current?.(id);
          });
          m.on("click", "regional-thermal", (e) => {
            const feature = e.features?.[0];
            const coordinates = feature?.geometry?.coordinates;
            if (!coordinates || coordinates.length < 2) return;
            const properties = feature.properties || {};
            const latitude = Number(coordinates[1]);
            const longitude = Number(coordinates[0]);
            const content = document.createElement("div");
            content.className = "thermal-popup";
            const heading = document.createElement("strong");
            heading.textContent = "NASA thermal anomaly";
            const description = document.createElement("p");
            description.textContent = `${properties.source || "NASA FIRMS / VIIRS"} · ${properties.observed_at ? new Date(properties.observed_at).toLocaleString() : "observation time unavailable"}`;
            const details = document.createElement("small");
            details.textContent = `Pixel center · ${latitude.toFixed(5)}, ${longitude.toFixed(5)}${properties.confidence ? ` · confidence ${properties.confidence}` : ""}${properties.distance_km ? ` · ${properties.distance_km} km from observer` : ""}`;
            const caveat = document.createElement("small");
            caveat.className = "thermal-popup-caveat";
            caveat.textContent = "A satellite heat pixel is not fire confirmation or a fire perimeter.";
            const actions = document.createElement("div");
            actions.className = "thermal-popup-actions";
            const observation = { ...properties, latitude, longitude, demo: false };
            for (const [label, action, style] of [
              ["Add to Evidence review + inbox", "add_to_review", ""],
              ["Mark for escalation", "escalated", ""],
              ["Confirm fire", "confirmed_fire", "primary"],
            ]) {
              const button = document.createElement("button");
              button.type = "button";
              button.className = style;
              button.textContent = label;
              button.addEventListener("click", () => {
                thermalAction.current?.({ action, observation });
                popup.remove();
              }, { once: true });
              actions.append(button);
            }
            content.append(heading, description, details, caveat, actions);
            const popup = new library.Popup({ closeButton: true, closeOnClick: true, maxWidth: "330px", offset: 14 })
              .setLngLat(coordinates)
              .setDOMContent(content)
              .addTo(m);
            e.preventDefault();
          });
          m.on("click", (e) => {
            if (suppressMapClick.current) {
              suppressMapClick.current = false;
              return;
            }
            mapPointPopup.current?.remove();
            mapPointPopup.current = null;
            const decisionPins = m.queryRenderedFeatures(e.point, { layers: ["decision-markers"] });
            if (decisionPins.length) {
              const reportId = decisionPins[0]?.properties?.report_id;
              if (reportId) selection.current?.(reportId);
              return;
            }
            const existing = m.queryRenderedFeatures(e.point, { layers: ["locations"] });
            if (existing.length) return;
            const point = { latitude: e.lngLat.lat, longitude: e.lngLat.lng };
            mapPointAction.current?.({ action: "plot", point });
            const content = document.createElement("div");
            content.className = "thermal-popup map-point-popup";
            const heading = document.createElement("strong");
            heading.textContent = "Map point analysis";
            const coordinates = document.createElement("small");
            coordinates.textContent = `${point.latitude.toFixed(5)}, ${point.longitude.toFixed(5)}`;
            const actions = document.createElement("div");
            actions.className = "thermal-popup-actions";
            const buttons = [
              ["Analyze terrain", "analyze", false],
              ["Use as affected area", "affected_area", false],
              ["Confirm fire", "confirmed_fire", false],
              ["Mark for escalation", "escalated", false],
            ];
            for (const [label, action, disabled] of buttons) {
              const button = document.createElement("button");
              button.type = "button";
              button.textContent = label;
              button.disabled = disabled;
              button.addEventListener("click", () => {
                const description = action === "confirmed_fire"
                  ? reportAvailable.current
                    ? "This records a human-confirmed fire for the selected report. This clicked point will not be assigned as the affected area; you can set an approximate area separately if useful. No authorities are contacted."
                    : "This creates a map-point inbox review and records your human fire confirmation. An affected-area point is optional and can be added later if useful. No image evidence is attached and no authorities are contacted."
                  : action === "escalated"
                    ? reportAvailable.current
                      ? "This marks the selected report for escalation review. It does not notify an agency."
                      : "This creates a map-point inbox review and marks it for escalation review. It does not notify an agency."
                    : action === "affected_area"
                      ? reportAvailable.current
                        ? "This sets the selected report’s working affected-area point for this session. It does not record a fire decision."
                        : "This creates an inbox map-point review and saves this as its working affected-area point. No fire decision is recorded."
                      : "This loads geographic and weather context for this point.";
                showActionConfirmation(popup, content, {
                  title: `Confirm: ${label}?`,
                  description: `${description} Coordinates: ${point.latitude.toFixed(5)}, ${point.longitude.toFixed(5)}.`,
                  onConfirm: () => mapPointAction.current?.({ action, point }),
                });
              }, { once: true });
              actions.append(button);
            }
            if (!reportAvailable.current) {
              const hint = document.createElement("small");
              hint.textContent = "Actions here can create a new map-point review in the inbox.";
              content.append(heading, coordinates, hint, actions);
            } else content.append(heading, coordinates, actions);
            const popup = new library.Popup({ closeButton: true, closeOnClick: false, maxWidth: "300px", offset: 14 })
              .setLngLat(e.lngLat)
              .setDOMContent(content)
              .addTo(m);
            mapPointPopup.current = popup;
            popup.on("close", () => {
              if (mapPointPopup.current === popup) mapPointPopup.current = null;
            });
          });
          const zoomToTerrainPoint = (e) => {
            const coordinates = e.features?.[0]?.geometry?.coordinates;
            if (!coordinates || coordinates.length < 2) return;
            e.preventDefault();
            setFlat(false);
            m.flyTo({
              center: coordinates,
              zoom: Math.min(13, Math.max(10.5, m.getZoom() + 1.8)),
              pitch: 56,
              duration: 700,
            });
          };
          for (const layer of ["locations", "regional-thermal", "inspection-point"]) {
            m.on("dblclick", layer, zoomToTerrainPoint);
          }
          m.on("mousedown", "scenario-edit-handles", (e) => {
            const feature = e.features?.[0];
            if (!feature || !scenarioForEdit.current) return;
            e.preventDefault();
            suppressMapClick.current = true;
            dragHandle.current = Number(feature.properties.vertex_index);
            const ring = scenarioForEdit.current.features[0]?.geometry?.coordinates?.[0];
            if (!ring) return;
            dragRing.current = ring.map((coordinate) => [...coordinate]);
            setDragPreviewRing(dragRing.current);
            m.getCanvas().style.cursor = "grabbing";
            m.dragPan.disable();
          });
          m.on("mousemove", (e) => {
            if (dragHandle.current == null || !dragRing.current) return;
            const index = dragHandle.current;
            const coordinate = [e.lngLat.lng, e.lngLat.lat];
            dragRing.current[index] = coordinate;
            if (index === 0) dragRing.current[dragRing.current.length - 1] = coordinate;
            setDragPreviewRing(dragRing.current.map((point) => [...point]));
            m.getCanvas().style.cursor = "grabbing";
          });
          const finishBoundaryDrag = () => {
            if (dragHandle.current == null) return;
            setEditedOuterRing(dragRing.current?.map((coordinate) => [...coordinate]) || null);
            setPendingBoundary(true);
            dragHandle.current = null;
            dragRing.current = null;
            setDragPreviewRing(null);
            m.dragPan.enable();
            m.getCanvas().style.cursor = "pointer";
          };
          m.on("mouseup", finishBoundaryDrag);
          m.on("mouseleave", finishBoundaryDrag);
          m.on("mousemove", (e) => {
            if (dragHandle.current != null) {
              m.getCanvas().style.cursor = "grabbing";
              return;
            }
            const handles = m.queryRenderedFeatures(e.point, { layers: ["scenario-edit-handles"] });
            const existing = m.queryRenderedFeatures(e.point, { layers: ["locations"] });
            m.getCanvas().style.cursor = handles.length ? "grab" : existing.length ? "pointer" : "crosshair";
          });
          m.on("mouseout", () => { m.getCanvas().style.cursor = ""; });
          m.on("mouseenter", "locations", () => {
            m.getCanvas().style.cursor = "pointer";
          });
          m.on("mouseleave", "locations", () => {
            m.getCanvas().style.cursor = "";
          });
          m.on("mouseenter", "regional-thermal", () => { m.getCanvas().style.cursor = "pointer"; });
          m.on("mouseleave", "regional-thermal", () => { m.getCanvas().style.cursor = ""; });
          m.on("mouseenter", "scenario-edit-handles", () => { m.getCanvas().style.cursor = "grab"; });
          m.on("mouseleave", "scenario-edit-handles", () => { m.getCanvas().style.cursor = ""; });
          setReady(true);
        });
      } catch {
        if (!disposed)
          setFatal(
            "Geographic map is unavailable in this browser. Reports and evidence remain accessible.",
          );
      }
    }
    initialize();
    return () => {
      disposed = true;
      observer?.disconnect();
      mapPointPopup.current?.remove();
      mapPointPopup.current = null;
      map.current = null;
      instance?.remove();
    };
  }, [token]);
  useEffect(() => {
    map.current?.getSource("incident")?.setData(incident?.geojson || EMPTY);
  }, [incident]);
  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    const changed = () => setViewportRevision((value) => value + 1);
    m.on("moveend", changed);
    return () => m.off("moveend", changed);
  }, [ready]);
  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    if (m.getLayer("calfire-hazard-fill")) {
      m.setLayoutProperty("calfire-hazard-fill", "visibility", hazardVisible ? "visible" : "none");
      m.setLayoutProperty("calfire-hazard-line", "visibility", hazardVisible ? "visible" : "none");
      m.setLayoutProperty("weekly-drought-fill", "visibility", droughtVisible ? "visible" : "none");
    }
  }, [ready, hazardVisible, droughtVisible]);
  useEffect(() => {
    const m = map.current;
    if (!ready || !m || !hazardVisible) return;
    if (m.getZoom() < 7) { setHazardStatus("Zoom in to level 7+ to query this layer"); m.getSource("calfire-hazard")?.setData(EMPTY); return; }
    const controller = new AbortController();
    setHazardStatus("Loading current viewport…");
    fetch(viewportQuery(FHSZ_QUERY, m.getBounds(), "FHSZ_Description,SRA"), { signal: controller.signal })
      .then((response) => { if (!response.ok) throw Error("CAL FIRE layer unavailable"); return response.json(); })
      .then((data) => {
        if (data.error || !Array.isArray(data.features)) throw Error("Unexpected CAL FIRE layer response");
        m.getSource("calfire-hazard")?.setData(data);
        setHazardStatus(`${data.features.length} mapped areas · CAL FIRE zoning vintage: SRA 2024 / LRA recommendations 2025 · checked ${new Date().toLocaleTimeString()}`);
      })
      .catch((error) => { if (error.name !== "AbortError") { m.getSource("calfire-hazard")?.setData(EMPTY); setHazardStatus("Unavailable · no hazard inference shown"); } });
    return () => controller.abort();
  }, [ready, hazardVisible, viewportRevision]);
  useEffect(() => {
    const m = map.current;
    if (!ready || !m || !droughtVisible) return;
    if (m.getZoom() < 7) { setDroughtStatus("Zoom in to level 7+ to query this layer"); m.getSource("weekly-drought")?.setData(EMPTY); return; }
    const controller = new AbortController();
    setDroughtStatus("Loading weekly map…");
    fetch(viewportQuery(DROUGHT_QUERY, m.getBounds(), "dm,update_dat"), { signal: controller.signal })
      .then((response) => { if (!response.ok) throw Error("Drought layer unavailable"); return response.json(); })
      .then((data) => {
        if (data.error || !Array.isArray(data.features)) throw Error("Unexpected drought layer response");
        m.getSource("weekly-drought")?.setData(data);
        const dates = [...new Set(data.features.map((feature) => feature.properties?.update_dat).filter(Boolean))];
        setDroughtStatus(data.exceededTransferLimit ? "Partial viewport result · zoom in · weekly USDM classifications" : `${data.features.length ? `${data.features.length} mapped areas` : "No drought polygons returned for this viewport"}${dates.length ? ` · data date ${dates[0]}` : " · source date unavailable"} · checked ${new Date().toLocaleTimeString()}`);
      })
      .catch((error) => { if (error.name !== "AbortError") { m.getSource("weekly-drought")?.setData(EMPTY); setDroughtStatus("Unavailable · no drought absence inferred"); } });
    return () => controller.abort();
  }, [ready, droughtVisible, viewportRevision]);
  useEffect(() => {
    map.current?.getSource("public-fires")?.setData(publicFires || EMPTY);
  }, [publicFires]);
  useEffect(() => {
    const point = inspectPoint
      ? { type: "FeatureCollection", features: [{ type: "Feature", properties: {},
          geometry: { type: "Point", coordinates: [inspectPoint.longitude, inspectPoint.latitude] } }] }
      : EMPTY;
    map.current?.getSource("inspection-point")?.setData(point);
  }, [inspectPoint]);
  const scenario = useMemo(
    () => confirmedFirePoint
      ? buildFireScenario(confirmedFirePoint, fireAssessment, scenarioPace)
      : null,
    [confirmedFirePoint?.latitude, confirmedFirePoint?.longitude, fireAssessment, scenarioPace],
  );
  useEffect(() => {
    setEditedOuterRing(null);
    setDragPreviewRing(null);
    setPendingBoundary(false);
  }, [scenario]);
  const displayScenario = useMemo(() => {
    if (!scenario) return null;
    const ring = dragPreviewRing || editedOuterRing;
    if (!ring) return scenario;
    const meanLatitude = ring.reduce((sum, point) => sum + point[1], 0) / ring.length;
    const projected = ring.map(([longitude, latitude]) => [
      longitude * 111.32 * Math.cos(meanLatitude * Math.PI / 180),
      latitude * 111.32,
    ]);
    const area = Math.abs(projected.slice(0, -1).reduce((sum, point, index) => {
      const next = projected[index + 1];
      return sum + point[0] * next[1] - next[0] * point[1];
    }, 0)) / 2;
    return {
      ...scenario,
      features: scenario.features.map((feature, index) => index === 0
        ? { ...feature, properties: { ...feature.properties, adjusted: true, area_km2: Number(area.toFixed(2)) }, geometry: { ...feature.geometry, coordinates: [ring] } }
        : feature),
    };
  }, [scenario, dragPreviewRing, editedOuterRing]);
  scenarioForEdit.current = displayScenario;
  useEffect(() => {
    map.current?.getSource("fire-scenario")?.setData(displayScenario || EMPTY);
    const ring = displayScenario?.features?.[0]?.geometry?.coordinates?.[0] || [];
    const handles = [];
    for (let index = 0; index < ring.length - 1; index += 6) {
      handles.push({
        type: "Feature",
        geometry: { type: "Point", coordinates: ring[index] },
        properties: { vertex_index: index },
      });
    }
    map.current?.getSource("scenario-edit-handles")?.setData({ type: "FeatureCollection", features: handles });
  }, [displayScenario, ready]);
  useEffect(() => {
    const mapInstance = map.current;
    const source = mapInstance?.getSource("scenario-front");
    const horizon = displayScenario?.features?.find((feature) => feature.properties?.minutes === 120);
    const ring = horizon?.geometry?.coordinates?.[0];
    if (!ready || !source || !ring?.length || !confirmedFirePoint) {
      source?.setData(EMPTY);
      return;
    }
    const origin = [confirmedFirePoint.longitude, confirmedFirePoint.latitude];
    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const durationMs = 9000;
    const start = performance.now();
    const renderFront = (progress) => {
      const eased = 1 - (1 - progress) ** 2;
      const scaledRing = ring.map(([longitude, latitude]) => [
        origin[0] + (longitude - origin[0]) * eased,
        origin[1] + (latitude - origin[1]) * eased,
      ]);
      source.setData({
        type: "FeatureCollection",
        features: [{
          type: "Feature",
          properties: { minutes: Math.round(progress * 120), progress },
          geometry: { type: "Polygon", coordinates: [scaledRing] },
        }],
      });
      mapInstance.setPaintProperty("scenario-front-fill", "fill-opacity", 0.2 + Math.sin(progress * Math.PI) * 0.18);
    };
    if (reducedMotion) {
      renderFront(1);
      return;
    }
    renderFront(0.025);
    const timer = window.setInterval(() => {
      const progress = Math.min((performance.now() - start) / durationMs, 1);
      renderFront(progress);
      if (progress >= 1) window.clearInterval(timer);
    }, 55);
    return () => window.clearInterval(timer);
  }, [displayScenario, ready, confirmedFirePoint?.latitude, confirmedFirePoint?.longitude]);
  useEffect(() => {
    if (!displayScenario || !ready) return;
    const timer = window.setInterval(() => {
      const mapInstance = map.current;
      if (!mapInstance?.getLayer("scenario-edge")) return;
      const pulse = 0.68 + 0.2 * (0.5 + 0.5 * Math.sin(Date.now() / 104));
      mapInstance.setPaintProperty("scenario-edge", "line-opacity", pulse);
      mapInstance.setPaintProperty("scenario-front-glow", "line-opacity", 0.2 + pulse * 0.34);
    }, 90);
    return () => window.clearInterval(timer);
  }, [displayScenario, ready]);
  useEffect(() => {
    if (!ready || !confirmedFirePoint) return;
    setFlat(false);
    map.current?.flyTo({
      center: [confirmedFirePoint.longitude, confirmedFirePoint.latitude],
      zoom: 12,
      pitch: 62,
      bearing: -25,
      duration: 1100,
    });
  }, [confirmedFirePoint?.latitude, confirmedFirePoint?.longitude, ready]);
  useEffect(() => {
    const features = publicFires?.features || [];
    if (!ready || !features.length || confirmedFirePoint) return;
    const coordinates = [];
    const visit = (value) => {
      if (!Array.isArray(value)) return;
      if (typeof value[0] === "number" && typeof value[1] === "number")
        coordinates.push(value);
      else value.forEach(visit);
    };
    features.forEach((feature) => visit(feature.geometry?.coordinates));
    if (focus && Number.isFinite(focus.longitude) && Number.isFinite(focus.latitude))
      coordinates.push([focus.longitude, focus.latitude]);
    if (!coordinates.length) return;
    const bounds = coordinates.reduce(
      (box, point) => [
        [Math.min(box[0][0], point[0]), Math.min(box[0][1], point[1])],
        [Math.max(box[1][0], point[0]), Math.max(box[1][1], point[1])],
      ],
      [[Infinity, Infinity], [-Infinity, -Infinity]],
    );
    map.current?.fitBounds(bounds, { padding: 72, maxZoom: 10, duration: 850 });
  }, [publicFires, ready, confirmedFirePoint?.latitude, confirmedFirePoint?.longitude]);
  useEffect(() => {
    if (ready && focus && !confirmedFirePoint) {
      setFlat(false);
      map.current?.flyTo({
        center: [focus.longitude, focus.latitude],
        zoom: 10,
        pitch: 40,
        duration: 900,
      });
    }
  }, [focus?.id, ready, confirmedFirePoint?.latitude, confirmedFirePoint?.longitude]);
  useEffect(() => {
    if (ready && replayFocus) {
      setFlat(false);
      map.current?.flyTo({ center: replayFocus, zoom: 8, pitch: 48, bearing: -15, duration: 900 });
    }
  }, [replayFocus?.[0], replayFocus?.[1], ready]);
  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    if (satelliteDate) {
      const tiles = [
        `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_CorrectedReflectance_TrueColor/default/${satelliteDate}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg`,
      ];
      if (!m.getSource("satellite")) {
        m.addSource("satellite", {
          type: "raster",
          tiles,
          tileSize: 256,
          maxzoom: 9,
          attribution: "NASA GIBS / Terra MODIS",
        });
        m.addLayer(
          {
            id: "satellite-image",
            type: "raster",
            source: "satellite",
            paint: { "raster-opacity": 0.9 },
          },
          "perimeter",
        );
      } else m.getSource("satellite").setTiles(tiles);
      m.setLayoutProperty("satellite-image", "visibility", "visible");
    } else if (m.getLayer("satellite-image"))
      m.setLayoutProperty("satellite-image", "visibility", "none");
  }, [satelliteDate, ready]);
  function toggleView() {
    const next = !flat;
    setFlat(next);
    map.current?.easeTo({
      pitch: next ? 0 : 62,
      bearing: next ? 0 : -25,
      duration: 700,
    });
  }
  function changeScale(value) {
    setTerrainScale(value);
    if (ready)
      map.current?.setTerrain({ source: "elevation", exaggeration: value });
  }
  return (
    <div className="terrain-wrapper">
      <div className="terrain-controls">
        <div>
          <strong>California evidence map</strong>
          <span>
            Reports, satellite detections & current perimeters · click California terrain to inspect conditions
          </span>
        </div>
        <div className="terrain-buttons">
          <label className="map-overlay-toggle"><input type="checkbox" checked={hazardVisible} onChange={(event) => setHazardVisible(event.target.checked)} /> CAL FIRE hazard</label>
          <label className="map-overlay-toggle"><input type="checkbox" checked={droughtVisible} onChange={(event) => setDroughtVisible(event.target.checked)} /> Weekly drought</label>
          <button disabled={!ready} onClick={toggleView}>
            {flat ? "3D terrain" : "Top-down"}
          </button>
          <button
            disabled={!ready}
            onClick={() => {
              setFlat(true);
              map.current?.flyTo({ ...HOME, duration: 1000 });
            }}
          >
            Reset view
          </button>
        </div>
      </div>
      {(hazardVisible || droughtVisible) && <div className="map-source-status" aria-live="polite">
        {hazardVisible && <span><b>CAL FIRE FHSZ</b> Long-term hazard zoning; not current incident probability. {hazardStatus} · <a href="https://data.ca.gov/@cal-fire/fire-hazard-severity-zone-viewer1" target="_blank" rel="noreferrer">Source and methods ↗</a></span>}
        {droughtVisible && <span><b>US Drought Monitor</b> Weekly drought context, separate from current weather and fire detection. {droughtStatus} · <a href="https://www.drought.gov/data-maps-tools/us-drought-monitor" target="_blank" rel="noreferrer">Source and cadence ↗</a></span>}
      </div>}
      {confirmedFirePoint && (
        <div className="spread-scenario-control" role="status">
          <div>
            <strong>Confirmed-fire terrain scenario</strong>
            <span>5× demo playback · an animated red front expands across terrain-adjusted 30 / 60 / 120 min envelopes.</span>
          </div>
          {scenario ? (
            <>
              <label>
                Demo base pace
                <input
                  type="range"
                  min="0.2"
                  max="1.5"
                  step="0.1"
                  value={scenarioPace}
                  onChange={(event) => setScenarioPace(Number(event.target.value))}
                />
                <b>{scenarioPace.toFixed(1)} km/h</b>
              </label>
              <p>
                Adjusted demo pace {scenario.metrics.paceKmPerHour} km/h ·
                Wind {scenario.metrics.windKmh} km/h from {scenario.metrics.windFromDegrees}° ·
                slope {scenario.metrics.slopeDegrees}° · mapped cover {scenario.metrics.vegetation}.
                The map pin is used as an origin proxy. Wind, point-local slope and mapped cover
                adjust the demo envelope. These are not measured spread velocity; missing fuels,
                fuel moisture, fire perimeter geometry and local fire behavior are not inferred.
              </p>
              <div className="spread-reach-readout">
                {displayScenario.features.slice().reverse().map((feature) => (
                  <span key={feature.properties.minutes}>
                    <b>{feature.properties.minutes} min</b>
                    <strong>{feature.properties.distance_km} km</strong>
                    <small>reach · ~{feature.properties.area_km2} km² footprint</small>
                  </span>
                ))}
              </div>
              <p className="scenario-edit-help">
                Drag a green handle on the 120-minute outline to propose a revised boundary. The green preview is an operator edit, not measured fire spread.
              </p>
              {pendingBoundary && (
                <div className="scenario-edit-confirm" role="alertdialog" aria-label="Confirm adjusted spread outline">
                  <strong>Save your adjusted outline?</strong>
                  <span>This records the edited scenario boundary for this map session.</span>
                  <div>
                    <button className="primary" onClick={() => setPendingBoundary(false)}>Confirm edit</button>
                    <button onClick={() => { setEditedOuterRing(null); setDragPreviewRing(null); setPendingBoundary(false); }}>Discard edit</button>
                  </div>
                </div>
              )}
              <small>
                Illustrative sensitivity view only—not a fire-growth forecast, arrival-time estimate,
                evacuation boundary or responder guidance. “Pace” is a user-set demo assumption.
              </small>
            </>
          ) : (
            <p>Load current terrain and weather context at the selected affected-area point to show the scenario. Missing inputs are left blank.</p>
          )}
        </div>
      )}
      <div className="map-stage terrain-stage">
        <div
          className="terrain-canvas"
          ref={target}
          style={fatal ? { display: "none" } : undefined}
        />
        {fatal && (
          <div className="map-loading">
            Map unavailable. Select a report from the inbox to review its
            evidence.
          </div>
        )}{" "}
        {!ready && !fatal && (
          <div className="map-loading">Loading geographic map & elevation…</div>
        )}
      </div>
      <div className="terrain-footer">
        <label htmlFor="elevationScale">
          Terrain relief <output>{terrainScale.toFixed(1)}×</output>
          <input
            id="elevationScale"
            type="range"
            min="1"
            max="3"
            step=".1"
            value={terrainScale}
            onChange={(e) => changeScale(+e.target.value)}
            disabled={!ready}
          />
        </label>
        <span>Drag to pan · scroll to zoom · right-drag to rotate & tilt</span>
      </div>
      {incident?.geojson?.features?.some(
        (feature) => feature.properties.kind === "report-match",
      ) && (
        <p className="map-match-note">
          Dashed links mark reports matching a distance/time screen. They do not confirm one incident; points show observer locations.
        </p>
      )}
      {(fatal || warning) && (
        <p className="map-error" role="status">
          {fatal || warning}
        </p>
      )}
    </div>
  );
}
