import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import Map from "./Map";
import CameraPanel from "./CameraPanel";
import Investigation from "./Investigation";
import EvidenceNetwork from "./EvidenceNetwork";
import LandscapeRisk from "./LandscapeRisk";
import ResponseResources from "./ResponseResources";
import HistoricalReplay from "./HistoricalReplay";
import OperatorGate from "./OperatorGate";
import "./workflow.css";
const fresh = () => ({
  latitude: "",
  longitude: "",
  direction: "",
  notes: "",
  observed_at: new Date().toISOString().slice(0, 16),
  image: null,
  video: null,
  demo: false,
  reference: false,
});
const statuses = {
  pending: "Awaiting review",
  escalated: "Escalation marked",
  dismissed: "Dismissed",
  needs_information: "More evidence needed",
  confirmed_fire: "Human-confirmed fire",
};
const time = (s) =>
  new Date(s).toLocaleString(undefined, { timeZoneName: "short" });
function geographicInboxLabel(report) {
  const assessment = report.geographic_assessment;
  if (report.reference) return "Geographic context · skipped for reference image";
  if (!assessment) return "Geographic context · not assessed";
  if (assessment.status === "pending") return "Geographic context · assessing";
  if (assessment.status === "not_assessed") return "Geographic context · not assessed for staged report";
  if (assessment.status !== "available") return "Geographic context · unavailable";
  const data = assessment.data || {};
  const cover = data.landscape?.cover || [];
  const woody = cover.filter((item) => ["forest", "wood", "scrub", "heath", "shrub"].includes(String(item).toLowerCase()));
  const fuel = woody.length
    ? `Mapped forest/woody fuels within 2 km of report point · ${woody.join(", ")}`
    : cover.length
      ? `Mapped vegetation within 2 km of report point · ${cover.join(", ")}`
      : data.landscape?.available
        ? "No forest/fuel tags mapped within 2 km of report point"
        : "Fuel mapping unavailable";
  const screen = data.screening;
  return `${fuel}${screen?.index != null ? ` · ${screen.label} ${screen.index}/100` : ""}`;
}
function externalReviewGuidance(opinion) {
  if (opinion?.agreement === "disagreement")
    return "The second review flagged a possible plume that the local screen did not. Inspect that area in the original image, then compare a nearby camera or a later frame before recording your decision.";
  if (opinion?.agreement === "both_flagged")
    return "Both reviews flagged a candidate. Check whether it persists across frames and inspect the original for cloud, steam, or light before recording a decision.";
  return "Neither review flagged a candidate. Inspect the full-resolution original and seek a fresh frame if visibility is limited; below-threshold results do not rule out smoke.";
}
class AppErrorBoundary extends React.Component {
  state = { error: null };
  static getDerivedStateFromError(error) {
    return { error };
  }
  componentDidCatch(error, info) {
    console.error("WildfireWatch interface failed to render", error, info);
  }
  render() {
    if (this.state.error)
      return (
        <main className="operator-gate">
          <section className="panel" role="alert" style={{ padding: 32, maxWidth: 760 }}>
            <span className="eyebrow">Interface error</span>
            <h1>WildfireWatch could not open this view.</h1>
            <p>The server is reachable, but the interface encountered a rendering error.</p>
            <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
              {this.state.error.message}
            </pre>
            <button className="primary" onClick={() => window.location.reload()}>
              Reload application
            </button>
          </section>
        </main>
      );
    return this.props.children;
  }
}
async function api(path, body) {
  const method = body ? "POST" : "GET";
  const r = await fetch(
    path,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {},
  );
  if (!r.ok) {
    if (r.status === 401)
      window.dispatchEvent(new Event("operator-session-expired"));
    const d = await r.json().catch(() => ({}));
    if (r.status === 405) {
      throw Error(
        `This server does not support ${method} ${path}. Reload the current WildfireWatch deployment and try again.`,
      );
    }
    throw Error(
      typeof d.detail === "string"
        ? d.detail
        : `Request failed (${r.status}) for ${path}. Check the connection and try again.`,
    );
  }
  return r.json();
}
function App() {
  const [view, setView] = useState("operator"),
    [activeTool, setActiveTool] = useState("map"),
    [caps, setCaps] = useState(null),
    [reports, setReports] = useState([]),
    [selected, setSelected] = useState(null),
    [cameraLocations, setCameraLocations] = useState([]),
    [fieldPlan, setFieldPlan] = useState(null),
    [sat, setSat] = useState({ observations: [] }),
    [fireContext, setFireContext] = useState(null),
    [investigationPacket, setInvestigationPacket] = useState(null),
    [form, setForm] = useState(fresh),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [events, setEvents] = useState([]),
    [weather, setWeather] = useState(null),
    [satellite, setSatellite] = useState(false),
    [date, setDate] = useState("2021-07-22"),
    [replayFocus, setReplayFocus] = useState(null),
    [filter, setFilter] = useState("all"),
    [notes, setNotes] = useState(""),
    [landscapePoint, setLandscapePoint] = useState(null),
    [placingObserver, setPlacingObserver] = useState(false),
    [fireAssessment, setFireAssessment] = useState(null),
    [responseLocation, setResponseLocation] = useState(null),
    [confirmFireOpen, setConfirmFireOpen] = useState(false),
    [connected, setConnected] = useState(false);
  const selection = useRef();
  selection.current = selected?.id;
  const selectedIncidentPoint = responseLocation?.reportId === selected?.id
    ? responseLocation
    : selected?.review?.incident_latitude != null && selected?.review?.incident_longitude != null
      ? { latitude: selected.review.incident_latitude, longitude: selected.review.incident_longitude }
      : null;
  const [videoPreview, setVideoPreview] = useState("");
  useEffect(() => {
    if (!form.video) {
      setVideoPreview("");
      return;
    }
    const url = URL.createObjectURL(form.video);
    setVideoPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [form.video]);
  useEffect(() => {
    let stopped = false,
      ws,
      retry;
    async function refresh() {
      try {
        const [c, r, s] = await Promise.all([
          api("/api/status"),
          api("/api/reports"),
          api("/api/satellite"),
        ]);
        if (!stopped) {
          setCaps(c);
          setReports(r.filter((r) => !r.demo || r.kind === "thermal_observation"));
          setSat(s);
        }
      } catch {
        if (!stopped)
          setMessage(
            "Interface preview only. Open the connected cloud application above, or run FastAPI locally, to analyze photos.",
          );
      }
    }
    refresh();
    function connect() {
      ws = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`,
      );
      ws.onopen = () => {
        setConnected(true);
        refresh();
      };
      ws.onmessage = (e) => {
        const v = JSON.parse(e.data);
        if (v.type === "report_stage")
          setEvents((a) => [...a.slice(-19), v.event]);
        if (v.type === "report_ready") {
          refresh();
          if (selection.current === v.report.id)
            api("/api/reports/" + v.report.id)
              .then(setSelected)
              .catch(() => {});
        }
      };
      ws.onclose = () => {
        setConnected(false);
        if (!stopped) retry = setTimeout(connect, 3000);
      };
      ws.onerror = () => {};
    }
    connect();
    return () => {
      stopped = true;
      clearTimeout(retry);
      ws?.close();
    };
  }, []);
  useEffect(() => {
    if (view !== "operator" || !caps?.local_vision_available) return;
    let stopped = false;
    async function refreshMissionData() {
      try {
        const mission = await api("/api/mission");
        if (stopped) return;
        setCameraLocations(mission.cameras || []);
        setFieldPlan(mission);
      } catch {
        // The map remains useful without the optional camera/report overlay.
      }
    }
    refreshMissionData();
    const timer = setInterval(refreshMissionData, 15000);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [caps?.local_vision_available, view]);
  async function choose(id) {
      setWeather(null);
      setNotes("");
      setActiveTool("review");
    setResponseLocation(null);
    setFireContext(null);
    setInvestigationPacket(null);
    try {
      const report = await api("/api/reports/" + id);
      setSelected(report);
    } catch (e) {
      setMessage(e.message);
    }
  }
  function upload(file) {
    if (!file) return;
    if (["video/mp4", "video/webm", "video/quicktime"].includes(file.type)) {
      if (file.size > 25 * 1024 * 1024) {
        setMessage("Choose a video under 25 MB and 90 seconds.");
        return;
      }
      setForm((v) => ({ ...v, image: null, video: file, demo: false }));
      return;
    }
    if (
      !["image/jpeg", "image/png", "image/webp"].includes(file.type) ||
      file.size > 5000000
    ) {
      setMessage("Choose a JPEG, PNG or WebP image under 5 MB.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () =>
      setForm((v) => ({
        ...v,
        image: reader.result,
        video: null,
        demo: false,
      }));
    reader.readAsDataURL(file);
  }
  async function submit(e) {
    e.preventDefault();
    if (!form.image && !form.video) {
      setMessage("Add a photo or a video first.");
      return;
    }
    if (!form.latitude || !form.longitude) {
      setMessage("Set the observer location with Use my location or Choose on map first.");
      return;
    }
    setBusy(true);
    setEvents([]);
    try {
      let r;
      if (form.video) {
        const params = new URLSearchParams({
          latitude: form.latitude,
          longitude: form.longitude,
          observed_at: form.observed_at + "Z",
          notes: form.notes,
          reference: String(form.reference),
          filename: form.video.name,
        });
        if (form.direction !== "") params.set("direction", form.direction);
        const response = await fetch(`/api/reports/video?${params}`, {
          method: "POST",
          headers: { "Content-Type": form.video.type },
          body: form.video,
        });
        if (response.status === 401)
          window.dispatchEvent(new Event("operator-session-expired"));
        if (!response.ok) {
          const detail = await response.json().catch(() => ({}));
          throw Error(detail.detail || "Video analysis failed.");
        }
        r = await response.json();
      } else {
        const p = {
          ...form,
          latitude: Number(form.latitude),
          longitude: Number(form.longitude),
          direction: form.direction === "" ? null : Number(form.direction),
          observed_at: form.observed_at + "Z",
        };
        delete p.source;
        delete p.video;
        r = await api("/api/reports", p);
      }
      setSelected(r);
      setReports((await api("/api/reports")).filter((r) => !r.demo || r.kind === "thermal_observation"));
      setView("operator");
      setActiveTool("review");
      setWeather(null);
      setForm(fresh());
      setMessage(
        `${form.video ? "Video frames analyzed" : "Photo analyzed"} and added to the local inbox. No emergency service was contacted.`,
      );
    } catch (e) {
      setMessage(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function review(decision, point = null, report = selected, decisionLocation = null) {
    if (!report) {
      setMessage("Select an inbox report or choose an action on a plotted map point.");
      return;
    }
    setBusy(true);
    try {
      const body = { decision, notes };
      const decisionPoint = point || selectedIncidentPoint;
      if (decision === "confirmed_fire" && decisionPoint) {
        body.incident_latitude = decisionPoint.latitude;
        body.incident_longitude = decisionPoint.longitude;
      }
      const markerPoint = decisionLocation || decisionPoint || {
        latitude: report.latitude,
        longitude: report.longitude,
      };
      if (markerPoint && Number.isFinite(Number(markerPoint.latitude)) && Number.isFinite(Number(markerPoint.longitude))) {
        body.decision_latitude = Number(markerPoint.latitude);
        body.decision_longitude = Number(markerPoint.longitude);
      }
      setSelected(
        await api(`/api/reports/${report.id}/review`, body),
      );
      setReports((await api("/api/reports")).filter((r) => !r.demo || r.kind === "thermal_observation"));
      setMessage(
        decision === "confirmed_fire"
          ? decisionPoint
            ? "Human confirmation saved. Nearby response-resource searches are ready; no authorities were contacted."
            : "Human confirmation saved. You can add an approximate affected-area point later; no authorities were contacted."
          : "Operator decision saved. Escalation is a status, not a notification to authorities.",
      );
    } catch (e) {
      setMessage(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function reviewThermal({ action, observation }) {
    setBusy(true);
    setWeather(null);
    setResponseLocation(null);
    setFireContext(null);
    setInvestigationPacket(null);
    try {
      let report = await api("/api/satellite/review", {
        observation_id: String(observation.id || `${observation.latitude},${observation.longitude},${observation.observed_at}`),
        latitude: Number(observation.latitude),
        longitude: Number(observation.longitude),
        observed_at: observation.observed_at,
        source: observation.source || "Satellite thermal observation",
        satellite: observation.satellite || "unknown",
        confidence: observation.confidence || "unknown",
        demo: observation.demo === true || observation.demo === "true",
      });
      if (action !== "add_to_review") {
        report = await api(`/api/reports/${report.id}/review`, {
          decision: action,
          notes: action === "confirmed_fire" ? "Operator confirmed after reviewing the satellite anomaly." : "Operator marked satellite anomaly for escalation review.",
          decision_latitude: Number(observation.latitude),
          decision_longitude: Number(observation.longitude),
          ...(action === "confirmed_fire" ? {
            incident_latitude: Number(observation.latitude),
            incident_longitude: Number(observation.longitude),
          } : {}),
        });
      }
      const [fullReport, updatedReports] = await Promise.all([
        api(`/api/reports/${report.id}`),
        api("/api/reports"),
      ]);
      setSelected(fullReport);
      setReports(updatedReports.filter((item) => !item.demo || item.kind === "thermal_observation"));
      setView("operator");
      setActiveTool("review");
      setMessage(action === "confirmed_fire"
        ? "Thermal anomaly marked human-confirmed. Its pixel center is shown as the approximate affected-area point; no authorities were contacted."
        : action === "escalated"
          ? "Thermal anomaly added to the inbox and marked for escalation review. No authorities were contacted."
          : "Thermal anomaly added to Evidence review and the inbox.");
      requestAnimationFrame(() => document.querySelector(".evidence-panel")?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }
  async function requestSecondOpinion() {
    setBusy(true);
    try {
      const report = await api(`/api/reports/${selected.id}/second-opinion`, {});
      setSelected(report);
      setReports((await api("/api/reports")).filter((r) => !r.demo || r.kind === "thermal_observation"));
      setMessage("External vision review recorded beside the local result. The scores were not combined.");
    } catch (e) {
      setMessage(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function currentWeather() {
    setBusy(true);
    try {
      setWeather(
        await api(
          `/api/location-context?latitude=${selected.latitude}&longitude=${selected.longitude}`,
        ),
      );
    } catch (e) {
      setMessage(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function refreshSatellite() {
    setBusy(true);
    try {
      setSat(await api("/api/satellite?live=true"));
      setMessage(
        "Latest available NASA thermal observations loaded. A hotspot is not a verified wildfire.",
      );
    } catch (e) {
      setMessage(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function importCSV(file) {
    if (!file) return;
    if (file.size > 5000000) {
      setMessage("CSV must be under 5 MB.");
      return;
    }
    try {
      await api("/api/satellite/import", { csv: await file.text() });
      setSat(await api("/api/satellite"));
      setMessage(
        "Imported California observations; file provenance is not independently verified.",
      );
    } catch (e) {
      setMessage(e.message);
    }
  }
  function locate() {
    if (!navigator.geolocation) {
      setMessage("Location access is unavailable in this browser. Choose the observer point on the map.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setPlacingObserver(false);
        setForm((v) => ({
          ...v,
          latitude: p.coords.latitude.toFixed(5),
          longitude: p.coords.longitude.toFixed(5),
          demo: false,
        }));
        setMessage(
          `Observer position recorded (accuracy approximately ${Math.round(p.coords.accuracy)} m). This does not locate the fire.`,
        );
      },
      () =>
        setMessage(
          "Location permission unavailable. Choose the observer point on the map instead.",
        ),
    );
  }
  async function mapPointAction({ action, point }) {
    if (action === "plot") {
      if (placingObserver) {
        if (point.latitude < 32 || point.latitude > 42.1 || point.longitude < -124.6 || point.longitude > -114) {
          setMessage("Choose an observer point within the California coverage area.");
          return;
        }
        setForm((value) => ({ ...value, latitude: point.latitude.toFixed(5), longitude: point.longitude.toFixed(5), demo: false }));
        setPlacingObserver(false);
        setMessage("Observer point set from the map.");
        return;
      }
      setLandscapePoint(point);
      return;
    }
    if (action === "analyze") {
      setLandscapePoint(point);
      setActiveTool("terrain");
      return;
    }
    if (!selected && ["affected_area", "confirmed_fire", "escalated"].includes(action)) {
      setBusy(true);
      try {
        const report = await api("/api/map-point-reports", {
          latitude: point.latitude,
          longitude: point.longitude,
          notes: "Created from a map point action. No image evidence was attached.",
          ...(action === "confirmed_fire" || action === "escalated"
            ? {
                action,
                decision_notes: action === "confirmed_fire"
                  ? "Operator confirmed the fire at the plotted point. No image evidence was attached; an affected-area boundary remains optional."
                  : "Operator marked the plotted point for escalation review; no image evidence is attached.",
              }
            : {}),
        });
        if (action === "affected_area") setResponseLocation({ reportId: report.id, ...point });
        else setResponseLocation(null);
        setSelected(report);
        setActiveTool("review");
        setSelected(report);
        setReports((await api("/api/reports")).filter((r) => !r.demo || r.kind === "thermal_observation"));
        setMessage(action === "affected_area"
          ? "Map point added to the inbox and set as the working affected area."
            : action === "confirmed_fire"
              ? "Human fire confirmation saved at the plotted point. An affected-area boundary is optional. No image evidence was attached and no authorities were contacted."
            : action === "escalated"
              ? "Map point added to the inbox and marked for escalation review. No authorities were contacted."
              : "Map point added to the inbox and marked as needing more evidence.");
      } catch (error) {
        setMessage(error.message);
      } finally {
        setBusy(false);
      }
      return;
    }
    if (!selected) return;
    if (action === "affected_area") {
      setResponseLocation({ reportId: selected.id, ...point });
      setMessage(`Affected-area point set to ${point.latitude.toFixed(4)}, ${point.longitude.toFixed(4)}.`);
      return;
    }
    if (["confirmed_fire", "escalated"].includes(action)) void review(action, null, selected, point);
  }
  const observations = sat.observations || [];
  const reportLinks = [];
  const linkedPairs = new Set();
  for (const item of fieldPlan?.queue || []) {
    for (const peer of item.nearby_reports || []) {
      const key = [item.id, peer.id].sort().join(":");
      if (linkedPairs.has(key)) continue;
      linkedPairs.add(key);
      reportLinks.push({
        type: "Feature",
        geometry: {
          type: "LineString",
          coordinates: [
            [item.longitude, item.latitude],
            [peer.longitude, peer.latitude],
          ],
        },
        properties: { kind: "report-match", name: "Possible report match" },
      });
    }
  }
  const geojson = {
    type: "FeatureCollection",
    features: [
      ...reportLinks.slice(0, 12),
      ...cameraLocations.map((c) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [c.longitude, c.latitude] },
        properties: { kind: "camera", camera_id: c.id, name: c.name },
      })),
      ...reports
        .filter((r) => !r.reference)
        .map((r) => ({
          type: "Feature",
          geometry: { type: "Point", coordinates: [r.longitude, r.latitude] },
          properties: {
            kind: "report",
            report_id: r.id,
            name: r.demo ? "Staged observer" : r.kind === "map_point_observation" ? "Map point review" : "Observer report",
          },
        })),
      ...reports
        .filter((r) => !r.reference && ["confirmed_fire", "escalated"].includes(r.status))
        .map((r) => {
          const review = r.review || {};
          const latitude = review.decision_latitude ?? review.incident_latitude ?? r.latitude;
          const longitude = review.decision_longitude ?? review.incident_longitude ?? r.longitude;
          const confirmed = r.status === "confirmed_fire";
          return {
            type: "Feature",
            geometry: { type: "Point", coordinates: [longitude, latitude] },
            properties: {
              kind: confirmed ? "confirmed_fire" : "escalated",
              report_id: r.id,
              name: confirmed ? "Confirmed report" : "Escalation marked",
              location_role: review.decision_latitude != null
                ? "operator-selected decision point"
                : review.incident_latitude != null
                  ? "operator-set affected-area point"
                  : r.location_role || "report location; not verified fire location",
            },
          };
        }),
      ...observations.map((h) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [h.longitude, h.latitude] },
        properties: {
          kind: "hotspot",
          name: h.demo ? "STAGED hotspot" : "Thermal anomaly",
          id: h.id,
          observed_at: h.observed_at,
          source: h.source,
          satellite: h.satellite,
          confidence: h.confidence,
          demo: h.demo,
        },
      })),
    ],
  };
  return (
    <div className={`ww-app ${view === "operator" ? "operator-app" : ""}`}>
      <header className="ww-header">
        <a className="brand" href="#">
          <span className="brand-mark">W</span>
          <span>
            WildfireWatch<small>Evidence before escalation</small>
          </span>
        </a>
        <nav aria-label="Workspace">
          <button
            className={view === "operator" ? "active" : ""}
            onClick={() => setView("operator")}
          >
            Operator workspace
          </button>
          <button
            className={view === "resident" ? "active" : ""}
            onClick={() => setView("resident")}
          >
            Report observed smoke
          </button>
        </nav>
        <span className={"connection " + (connected ? "online" : "")}>
          {connected
            ? "Live updates connected"
            : caps
              ? "Live updates reconnecting"
              : "Interface preview · backend unavailable"}
        </span>
      </header>
      <div className="prototype-bar">
        RESEARCH PROTOTYPE{" "}
        <span>
          Reports stay in this installation. This is not an official emergency
          channel. For an immediate emergency, contact emergency services.
        </span>
      </div>
      {message && (
        <div className="notice" role="status">
          {message}
          <button aria-label="Dismiss message" onClick={() => setMessage("")}>
            ×
          </button>
        </div>
      )}
      {confirmFireOpen && selected && (
        <div className="fire-confirm-backdrop" onMouseDown={(event) => {
          if (event.target === event.currentTarget) setConfirmFireOpen(false);
        }}>
          <section className="fire-confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="fire-confirm-title" aria-describedby="fire-confirm-description">
            <span className="eyebrow">HUMAN REVIEW</span>
            <h2 id="fire-confirm-title">Confirm this fire report?</h2>
            <p id="fire-confirm-description">
              {selectedIncidentPoint
                ? `This records your confirmation with the current approximate map point (${selectedIncidentPoint.latitude.toFixed(4)}, ${selectedIncidentPoint.longitude.toFixed(4)}). You can update that point as the affected area becomes clearer.`
                : "An affected-area point is optional. If this may be an early warning and no area has been affected or mapped yet, you can confirm the report now and add an approximate point later."}
            </p>
            <div className="fire-confirm-actions">
              <button disabled={busy} onClick={() => setConfirmFireOpen(false)}>Go back</button>
              <button className="primary" disabled={busy} onClick={() => {
                setConfirmFireOpen(false);
                void review("confirmed_fire");
              }}>Confirm fire now</button>
            </div>
          </section>
        </div>
      )}
      {view === "resident" ? (
        <main className="resident-layout">
          <section className="resident-intro">
            <span className="eyebrow">Community evidence</span>
            <h1>
              Already seeing smoke?
              <br />
              Share what you observed.
            </h1>
            <p>
              A photo or short video helps an operator review possible smoke
              alongside other observations. Submit only from a safe place. Do
              not approach a fire or stop on a roadway to record it.
            </p>
            <div className="how-card">
              <h3>What happens next</h3>
              <ol>
                <li>
                  Your media and observer position enter the review queue.
                </li>
                <li>Our trained model highlights possible smoke.</li>
                <li>
                  An operator compares the evidence and records a decision.
                </li>
              </ol>
              <p>
                No report is automatically confirmed or sent to authorities.
              </p>
            </div>
            <button className="text-button" onClick={() => setView("operator")}>
              ← Back to operator workspace
            </button>
          </section>
          <form className="report-form" onSubmit={submit}>
            <div className="section-head">
              <h2>Observation report</h2>
              <span>{"PHOTO OR VIDEO SUBMISSION"}</span>
            </div>
            <label className="upload-area">
              {form.video ? (
                <video src={videoPreview} muted playsInline />
              ) : form.image ? (
                <img src={form.image} alt="Photo to submit for smoke review" />
              ) : (
                <>
                  <b>＋ Add a photo or video</b>
                  <span>
                    Photo: JPEG, PNG, WebP · 5 MB. Video: MP4, WebM, MOV · 25 MB
                    · 90 sec.
                  </span>
                </>
              )}
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp,video/mp4,video/webm,video/quicktime"
                onChange={(e) => upload(e.target.files[0])}
              />
            </label>
            <p className="field-help">
              The original clip and sampled frames stay in this backend
              installation. Up to six evenly spaced frames are analyzed; short
              events between samples may be missed. Avoid faces, license plates,
              and personal details. The model screens for smoke; it does not
              confirm fire or flames.
            </p>
            <div className="form-heading">
              <h3>Observer location</h3>
              <div className="button-row">
                <button type="button" onClick={locate}>Use my location</button>
                <button type="button" onClick={() => {
                  setPlacingObserver(true);
                  setMessage("Click the map to set where you were standing.");
                }}>{placingObserver ? "Click the map…" : "Choose on map"}</button>
              </div>
            </div>
            <p className="field-help" aria-live="polite">
              {placingObserver
                ? "Choose the observer point on the map. This is not the fire location."
                : form.latitude && form.longitude
                  ? `Observer point: ${Number(form.latitude).toFixed(5)}, ${Number(form.longitude).toFixed(5)} · California coverage. This is not the fire location.`
                  : "Set your observer point with one of the options above. Your position is not assumed to be the fire location."}
            </p>
            <div className="two-fields">
              <label>
                Observation time (UTC)
                <input
                  required
                  type="datetime-local"
                  value={form.observed_at}
                  onChange={(e) =>
                    setForm({ ...form, observed_at: e.target.value })
                  }
                />
              </label>
              <label>
                Looking toward (degrees, optional)
                <input
                  type="number"
                  min="0"
                  max="360"
                  placeholder="0 north · 90 east"
                  value={form.direction}
                  onChange={(e) =>
                    setForm({ ...form, direction: e.target.value })
                  }
                />
              </label>
            </div>
            <label>
              What did you observe?
              <textarea
                maxLength="1000"
                placeholder="Describe smoke, landmarks, and visibility."
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
              />
            </label>
            <label>
              <input
                type="checkbox"
                checked={form.reference}
                onChange={(e) =>
                  setForm({ ...form, reference: e.target.checked })
                }
              />{" "}
              Reference media · supplied location/time are test values
            </label>
            {form.reference && (
              <p className="field-help">
                This media will be analyzed, but test coordinates will not
                appear on the observation map or match satellite detections.
              </p>
            )}
            <button
              className="primary"
              disabled={busy || !caps?.local_vision_available}
            >
              {busy
                ? form.video
                  ? "Analyzing sampled video frames…"
                  : "Analyzing photo…"
                : "Submit for local review →"}
            </button>
            {!caps?.local_vision_available && (
              <p className="field-help">
                Connect to the backend with its trained detector to submit
                reports.
              </p>
            )}
          </form>
        </main>
      ) : (
        <main className="operator-layout map-command-center" data-tool={activeTool}>
          <nav className="map-tool-rail" aria-label="Map workspace tools">
            {[
              ["map", "⌖", "Map"],
              ["inbox", "▤", `Inbox${reports.filter((report) => report.status === "pending").length ? ` · ${reports.filter((report) => report.status === "pending").length}` : ""}`],
              ["review", "✓", "Evidence review"],
              ["investigation", "⤧", "Investigation"],
              ["signals", "⌁", "Evidence network"],
              ["terrain", "◈", "Terrain & risk"],
              ["camera", "◉", "Live camera"],
              ["replay", "▷", "Historical replay"],
              ["audit", "ⓘ", "Activity & limits"],
            ].map(([tool, icon, label]) => (
              <button key={tool} type="button" className={`map-tool-button ${activeTool === tool ? "active" : ""}`} aria-label={label} aria-pressed={activeTool === tool} title={label} onClick={() => setActiveTool(tool)}>
                <span aria-hidden="true">{icon}</span>
              </button>
            ))}
            <span className="map-tool-divider" />
            <button type="button" className="map-tool-button map-tool-new" aria-label="New observation" title="New observation" onClick={() => setView("resident")}>
              <span aria-hidden="true">＋</span>
            </button>
          </nav>
          <div className="map-command-hud">
            <span className="eyebrow">CALIFORNIA · EVIDENCE MAP</span>
            <strong>WildfireWatch</strong>
            <small>{connected ? "Live updates connected" : "Research workspace · human review required"}</small>
          </div>
          <div className="workspace-title">
            <div>
              <span className="eyebrow">
                California · single-operator research workspace
              </span>
              <h1>Evidence to action.</h1>
              <p>
                Monitor a camera, inspect the evidence, and record a human
                decision.
              </p>
            </div>
            <button className="primary" onClick={() => setView("resident")}>
              ＋ New observation
            </button>
          </div>
          {selected && investigationPacket?.reportId === selected.id && (
            <div className={`floating-tool-panel ${activeTool === "signals" ? "workspace-tool-open" : ""}`}>
            <EvidenceNetwork
              report={selected}
              packet={investigationPacket.data}
              regional={fireContext?.reportId === selected.id ? fireContext.data : null}
              context={weather}
            />
            </div>
          )}
          <HistoricalReplay onReplay={({ date: replayDate, center }) => {
            setDate(replayDate);
            setSatellite(true);
            setReplayFocus(center);
          }} className={activeTool === "replay" ? "workspace-tool-open" : ""} />
          <CameraPanel
            available={!!caps?.local_vision_available}
            api={api}
            onReport={choose}
            className={activeTool === "camera" ? "workspace-tool-open" : ""}
          />
          <div className="workspace-grid">
            <aside className={`inbox panel ${activeTool === "inbox" ? "workspace-tool-open" : ""}`}>
              <div className="section-head">
                <h2>02 · Review inbox</h2>
                <select
                  aria-label="Filter reports"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                >
                  <option value="all">All reports</option>
                  <option value="pending">Awaiting review</option>
                </select>
              </div>
              {reports
                .filter((r) => filter === "all" || r.status === "pending")
                .map((r) => (
                  <button
                    className={
                      "report-item " + (selected?.id === r.id ? "selected" : "")
                    }
                    key={r.id}
                    onClick={() => choose(r.id)}
                  >
                    <div>
                      <span className={"status " + r.status}>
                        {statuses[r.status]}
                      </span>
                      {r.reference && (
                        <span className="demo-tag">REFERENCE</span>
                      )}
                      {r.provenance?.kind === "public_camera" && (
                        <span className="demo-tag">CAMERA</span>
                      )}
                      {r.video_evidence && (
                        <span className="demo-tag">VIDEO</span>
                      )}
                      {r.kind === "thermal_observation" && <span className="demo-tag">THERMAL</span>}
                      {r.kind === "map_point_observation" && <span className="demo-tag">MAP POINT</span>}
                      {r.kind === "thermal_observation" && r.demo && <span className="demo-tag">STAGED</span>}
                    </div>
                    <b>{r.kind === "map_point_observation" ? "Map point review" : r.kind === "thermal_observation" ? "Thermal anomaly" : r.finding?.smoke_detected ? "Possible smoke" : "No smoke above threshold"}</b>
                    <small>
                      {r.latitude.toFixed(3)}, {r.longitude.toFixed(3)} · {r.kind === "thermal_observation" ? "pixel center" : r.kind === "map_point_observation" ? "plotted map point" : "observer"}
                    </small>
                    <small>{time(r.observed_at)}</small>
                    {r.kind === "thermal_observation" ? <small>{r.thermal_observation?.source || "Satellite source"} · not confirmation</small> : <div className="report-score">
                      {r.kind === "map_point_observation" ? "No image evidence attached" : <>Model score {r.finding?.confidence == null ? "—" : `${Math.round(r.finding.confidence * 100)}%`}<span>{r.matches?.length || 0} nearby observations</span></>}
                    </div>}
                    <small className="geographic-inbox-label">{geographicInboxLabel(r)}</small>
                  </button>
                ))}
              {!reports.filter(
                (r) => filter === "all" || r.status === "pending",
              ).length && (
                <div className="empty">
                  <span>◎</span>
                  <h3>No reports in this view</h3>
                  <p>Submit an observation to see the review workflow.</p>
                </div>
              )}
            </aside>
            <section className="map-panel panel">
              <div className="section-head">
                <h2>Find an independent view</h2>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={satellite}
                    onChange={(e) => setSatellite(e.target.checked)}
                  />
                  Satellite imagery
                </label>
              </div>
              {satellite && (
                <div className="satellite-date">
                  <label>
                    NASA Terra MODIS date{" "}
                    <input
                      type="date"
                      value={date}
                      max={new Date().toISOString().slice(0, 10)}
                      onChange={(e) => setDate(e.target.value)}
                    />
                  </label>
                  <span>
                    Historical true-color imagery · not analyzed by YOLO
                  </span>
                </div>
              )}
              <Map
                incident={{ geojson }}
                focus={selected?.reference ? null : selected}
                onSelect={choose}
                onThermalAction={reviewThermal}
                onMapPointAction={mapPointAction}
                hasSelectedReport={Boolean(selected)}
                onTerrainInspect={(point) => {
                  if (placingObserver) {
                    if (point.latitude < 32 || point.latitude > 42.1 || point.longitude < -124.6 || point.longitude > -114) {
                      setMessage("Choose an observer point within the California coverage area.");
                      return;
                    }
                    setForm((value) => ({ ...value, latitude: point.latitude.toFixed(5), longitude: point.longitude.toFixed(5), demo: false }));
                    setPlacingObserver(false);
                    setMessage("Observer point set from the map. This is separate from the fire location.");
                    return;
                  }
                  setLandscapePoint(point);
                  setActiveTool("terrain");
                }}
                inspectPoint={landscapePoint}
                onCamera={async (id) => {
                  try {
                    setActiveTool("camera");
                    await api("/api/camera/select", { camera_id: id });
                    setMessage(
                      "Camera selected. Start monitoring to collect fresh evidence.",
                    );
                  } catch (e) {
                    setMessage(e.message);
                  }
                }}
                satelliteDate={satellite ? date : null}
                replayFocus={replayFocus}
                publicFires={
                  fireContext &&
                  selected &&
                  fireContext.reportId === selected.id
                    ? fireContext.data.map
                    : null
                }
                confirmedFirePoint={selected?.status === "confirmed_fire" ? selectedIncidentPoint : null}
                fireAssessment={
                  fireAssessment &&
                  selectedIncidentPoint &&
                  Math.abs(fireAssessment.location.latitude - selectedIncidentPoint.latitude) < 0.00001 &&
                  Math.abs(fireAssessment.location.longitude - selectedIncidentPoint.longitude) < 0.00001
                    ? fireAssessment
                    : null
                }
              />
              <div className="map-legend">
                <span>
                  <i className="observer-dot" />
                  Observer report
                </span>
                <span>
                  <i className="thermal-dot" />
                  Thermal observation
                </span>
                <span>
                  <i className="confirmed-fire-dot" />
                  Fire confirmed
                </span>
                <span>
                  <i className="escalation-dot" />
                  Escalation marked
                </span>
                <span>
                  <i className="perimeter-dot" />
                  NIFC current perimeter
                </span>
                {selected?.status === "confirmed_fire" && (
                  <span>
                    <i className="scenario-dot" />
                    Illustrative scenario envelope
                  </span>
                )}
              </div>
              <details className="satellite-source">
                <summary>NASA thermal · {sat.observations?.length || 0} loaded</summary>
                <p>
                  {sat.observations?.length || 0} loaded California
                  observations. Thermal anomalies can have non-wildfire causes.
                  Imagery and hotspot data are separate products.
                </p>
                <button disabled={busy} onClick={refreshSatellite}>
                  Refresh NASA FIRMS
                </button>
                <label className="file-button">
                  Import FIRMS CSV
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    onChange={(e) => importCSV(e.target.files[0])}
                  />
                </label>
                <p>
                  Live refresh requires configured satellite access. Imported
                  CSV provenance is not independently verified.{" "}
                  <a
                    href="https://firms.modaps.eosdis.nasa.gov/"
                    target="_blank"
                    rel="noreferrer"
                  >
                    NASA FIRMS ↗
                  </a>
                </p>
              </details>
            </section>
          </div>
          <LandscapeRisk
            point={landscapePoint}
            className={activeTool === "terrain" ? "workspace-tool-open" : ""}
            onAssessment={setFireAssessment}
            onUseAsIncidentLocation={selected ? (point) => {
              setResponseLocation({ reportId: selected.id, ...point });
              setMessage(`Optional affected-area point set to ${point.latitude.toFixed(4)}, ${point.longitude.toFixed(4)}.`);
            } : null}
          />
          <section className={`evidence-panel panel ${activeTool === "review" ? "workspace-tool-open" : ""}`}>
            <div className="section-head">
              <h2>
                {selected
                  ? "Evidence review"
                  : "Select a report to investigate"}
              </h2>
              {selected && (
                <span>
                  {statuses[selected.status]} · {selected.id}
                </span>
              )}
            </div>
            {selected ? (
              <div className="evidence-grid">
                <div>
                  {selected.kind === "thermal_observation" ? <div className="thermal-evidence-card">
                    <span className="eyebrow">SATELLITE THERMAL PIXEL</span>
                    <strong>{selected.thermal_observation?.source || "Satellite thermal observation"}</strong>
                    <span>{selected.thermal_observation?.satellite || "Satellite unavailable"} · {selected.thermal_observation?.confidence || "Confidence unavailable"}</span>
                    <b>{selected.latitude.toFixed(5)}, {selected.longitude.toFixed(5)}</b>
                    <small>{time(selected.observed_at)} · pixel center, not a verified perimeter</small>
                  </div> : selected.kind === "map_point_observation" ? <div className="thermal-evidence-card">
                    <span className="eyebrow">OPERATOR-PLOTTED MAP POINT</span>
                    <strong>No image or video attached</strong>
                    <span>This inbox entry records a location and operator action only.</span>
                    <b>{selected.latitude.toFixed(5)}, {selected.longitude.toFixed(5)}</b>
                    <small>{time(selected.observed_at)} · not an automated fire detection</small>
                  </div> : <div className="evidence-image">
                    <img
                      src={selected.image}
                      alt="Submitted evidence with model smoke candidate boxes"
                    />
                    {(selected.finding?.boxes || [])
                      .filter((b) => b.score >= 0.25)
                      .map((b, i) => (
                        <div
                          key={i}
                          className="detection-box"
                          style={{
                            left: b.xyxy_normalized[0] * 100 + "%",
                            top: b.xyxy_normalized[1] * 100 + "%",
                            width:
                              (b.xyxy_normalized[2] - b.xyxy_normalized[0]) *
                                100 +
                              "%",
                            height:
                              (b.xyxy_normalized[3] - b.xyxy_normalized[1]) *
                                100 +
                              "%",
                          }}
                        >
                          <span className="sr-only">
                            Smoke candidate {Math.round(b.score * 100)}%
                          </span>
                        </div>
                      ))}
                  </div>}
                  {selected.kind !== "thermal_observation" && selected.kind !== "map_point_observation" && <p className="field-help">
                    {(selected.finding?.boxes || [])
                      .filter((b) => b.score >= 0.25)
                      .map(
                        (b, i) =>
                          `Region ${i + 1}: smoke candidate ${Math.round(b.score * 100)}%`,
                      )
                      .join(" · ") || "No candidate regions."}{" "}
                    Labels are below the image to preserve visibility.
                    Predictions are not operator confirmation.
                  </p>}
                  {selected.video_evidence && (
                    <section
                      className="video-evidence-review"
                      aria-label="Video analysis evidence"
                    >
                      <div className="section-head">
                        <div>
                          <b>
                            Video evidence ·{" "}
                            {selected.video_evidence.frames_analyzed} sampled
                            frames
                          </b>
                          <small>
                            {selected.provenance?.filename} ·{" "}
                            {selected.video_evidence.duration_seconds}s ·{" "}
                            {selected.video_evidence.frames_flagged} above
                            threshold
                          </small>
                        </div>
                        <span>Local smoke model</span>
                      </div>
                      <video
                        controls
                        preload="metadata"
                        src={`/api/reports/${selected.id}/video`}
                        aria-label="Original uploaded video"
                      />
                      <div className="video-frame-grid">
                        {selected.video_evidence.frames.map((frame) => (
                          <figure key={frame.offset_seconds}>
                            <img
                              src={frame.image}
                              alt={`Sample at ${frame.offset_seconds} seconds`}
                            />
                            <figcaption>
                              <b>{frame.offset_seconds.toFixed(1)}s</b>
                              <span>
                                {frame.smoke_detected
                                  ? "Possible smoke"
                                  : "Below threshold"}{" "}
                                · {Math.round(frame.confidence * 100)}%
                                uncalibrated
                              </span>
                            </figcaption>
                          </figure>
                        ))}
                      </div>
                      <p className="field-help">
                        {selected.video_evidence.sampling_note} These are
                        screening results, not fire confirmation.
                      </p>
                    </section>
                  )}
                  {selected.reference && (
                    <p className="field-help">
                      Reference media. Supplied location/time are test values,
                      not the original capture location/time.
                    </p>
                  )}
                  {selected.provenance?.kind === "public_camera" && (
                    <p className="field-help">
                      Public camera: {selected.provenance.name}. Image credit:{" "}
                      <a
                        href={selected.provenance.page}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {selected.provenance.credit}
                      </a>
                      . Provider update{" "}
                      {time(selected.provenance.provider_updated_at)}; original
                      capture timestamp remains visible on the unmodified image.
                    </p>
                  )}
                  <p>{selected.notes || "No observer notes supplied."}</p>
                </div>
                <div className="assessment">
                  <section className="geographic-assessment-card" aria-label="Geographic and environmental screening">
                    <div className="section-head">
                      <div>
                        <span className="eyebrow">LOCATION CONTEXT</span>
                        <h3>Terrain & wildfire fuels</h3>
                      </div>
                      <span className={`geo-state ${selected.geographic_assessment?.status || "pending"}`}>
                        {selected.geographic_assessment?.status === "available" ? "Loaded" : selected.geographic_assessment?.status === "unavailable" ? "Unavailable" : selected.geographic_assessment?.status === "not_assessed" || !selected.geographic_assessment ? "Not assessed" : "Assessing"}
                      </span>
                    </div>
                    {selected.geographic_assessment?.status === "available" ? (() => {
                      const geo = selected.geographic_assessment.data || {};
                      const cover = geo.landscape?.cover || [];
                      const woody = cover.filter((item) => ["forest", "wood", "scrub", "heath", "shrub"].includes(String(item).toLowerCase()));
                      const factors = geo.screening?.factors || [];
                      const factor = (name) => factors.find((item) => item.name === name);
                      const vegetation = factor("Mapped vegetation");
                      return <>
                        <b>{woody.length ? `Mapped forest/woody fuels within 2 km of report point: ${woody.join(", ")}` : vegetation?.available ? (cover.length ? `Other mapped vegetation within 2 km of report point: ${cover.join(", ")}` : "No forest/fuel tags mapped within 2 km of report point") : "Fuel mapping unavailable"}</b>
                        <p>{geo.screening?.label || "Environmental screen"}{geo.screening?.index != null ? ` · ${geo.screening.index}/100 · ${geo.screening.coverage_percent}% factor coverage` : " · insufficient data"}</p>
                        <p>{[factor("Terrain slope"), factor("Relative humidity"), factor("7-day precipitation"), factor("Wind"), factor("Air temperature")].filter((item) => item?.available).map((item) => `${item.name}: ${item.value}`).join(" · ") || "Terrain and weather factors unavailable"}</p>
                        <small>Coordinates: {Number(geo.location?.latitude ?? selected.latitude).toFixed(4)}, {Number(geo.location?.longitude ?? selected.longitude).toFixed(4)} · {selected.location_role || "report point"}. For photo/camera reports this may be the observer position, not the fire location. Assessed {time(geo.assessed_at)}; weather reflects assessment time. Fuel maps are incomplete; this is not a fire probability and does not change the image score.</small>
                      </>;
                    })() : <p>{selected.geographic_assessment?.status === "unavailable" ? (selected.geographic_assessment.message || "Public geographic sources could not be retrieved; no values were substituted.") : selected.geographic_assessment?.status === "not_assessed" ? (selected.geographic_assessment.message || "This staged report was not assessed.") : selected.reference || !selected.geographic_assessment ? "Reference or older report: no automatic geographic assessment is attached." : "Loading mapped fuels, terrain, weather, and alert context for this California point."}</p>}
                  </section>
                  <h3>
                    {selected.kind === "map_point_observation"
                      ? "Map point · operator review required"
                      : selected.kind === "thermal_observation"
                      ? "Thermal anomaly · human review required"
                      : selected.finding?.smoke_detected
                      ? selected.video_evidence
                        ? "Possible smoke in video · review required"
                        : "Possible smoke requires review"
                      : selected.video_evidence
                        ? "No candidate in sampled frames"
                        : "No smoke detected above threshold"}
                  </h3>
                  <p>{selected.finding?.reason}</p>
                  {selected.kind !== "thermal_observation" && selected.kind !== "map_point_observation" && <section className="external-review" aria-labelledby="external-review-title">
                    <div className="external-review-heading">
                      <div>
                        <span className="eyebrow">OPTIONAL SECOND REVIEW</span>
                        <h4 id="external-review-title">External image review</h4>
                      </div>
                      <span className={`model-status ${selected.external_opinion ? "available" : caps?.external_vision_available ? "available" : "unavailable"}`}>
                        {selected.external_opinion ? "Review recorded" : caps?.external_vision_available ? "Available on request" : "Not configured"}
                      </span>
                    </div>
                    {selected.external_opinion ? (
                      <div className="external-review-guidance">
                        <b>Recommended check</b>
                        <p>{externalReviewGuidance(selected.external_opinion)}</p>
                      </div>
                    ) : (
                      <>
                        <button className="primary" disabled={busy || !caps?.external_vision_available} onClick={requestSecondOpinion}>
                          {busy ? "Reviewing…" : "Request external second opinion"}
                        </button>
                        <p className="field-help">
                          {caps?.external_vision_available
                            ? `Sends ${selected.video_evidence ? "up to 2 sampled frames" : "this image"} to OpenAI on request. Advisory only; no alerts.`
                            : "Unavailable; server key not configured."}
                        </p>
                      </>
                    )}
                  </section>}
                  <dl>
                    <dt>{selected.kind === "thermal_observation" ? "Thermal pixel center" : selected.kind === "map_point_observation" ? "Plotted map point" : "Observer position"}</dt>
                    <dd>
                      {selected.latitude.toFixed(4)},{" "}
                      {selected.longitude.toFixed(4)}
                    </dd>
                    <dt>Viewing direction</dt>
                    <dd>
                      {selected.direction == null
                        ? "Not supplied"
                        : selected.direction + "°"}
                    </dd>
                    <dt>Observation</dt>
                    <dd>{time(selected.observed_at)}</dd>
                  </dl>
                  <p>
                    <a href="#investigation">
                      Open investigation: temporal evidence, next camera &
                      downloadable packet
                    </a>
                  </p>
                  <h4>Satellite corroboration</h4>
                  {selected.matches?.length ? (
                    selected.matches.map((h) => (
                      <p className="match" key={h.id}>
                        {h.source} · {h.distance_km} km from observer ·{" "}
                        {h.time_difference_hours} h apart
                        <br />
                        <small>
                          {h.demo
                            ? "STAGED — not a NASA detection"
                            : "Thermal anomaly — not verified as wildfire"}
                        </small>
                      </p>
                    ))
                  ) : (
                    <p>
                      No loaded observation within 25 km / 24 hours. This does
                      not rule out a fire.
                    </p>
                  )}
                  <p className="field-help">
                    Distance/time matching does not establish the same fire or
                    triangulate ignition.
                  </p>
                  <button
                    disabled={busy || selected.reference}
                    onClick={currentWeather}
                  >
                    {selected.reference
                      ? "Capture location unknown · geographic context unavailable"
                      : "Load geographic & weather context"}
                  </button>
                  {weather && (
                    <div className="weather">
                      <div className="weather-heading">
                        <h3>Observer-area context</h3>
                        <span>Not fire-site conditions</span>
                      </div>
                      <div className="weather-facts">
                        <span><b>Wind</b>{weather.current.wind_speed_10m} {weather.units.wind_speed_10m} · {weather.current.wind_direction_10m}°</span>
                        <span><b>Humidity</b>{weather.current.relative_humidity_2m}%</span>
                        <span><b>Temperature</b>{weather.current.temperature_2m ?? "—"} {weather.units.temperature_2m ?? "°C"}</span>
                        <span><b>Precipitation</b>{weather.current.precipitation ?? "—"} {weather.units.precipitation ?? "mm"}</span>
                      </div>
                      <p className="weather-landscape">
                        Terrain {weather.elevation_m ?? "—"} m · Cover: {weather.geography.available
                          ? weather.geography.cover.join(", ") || "no mapped tags"
                          : "unavailable"} · Development: {weather.geography.available
                            ? `${weather.geography.buildings} buildings / ${weather.geography.developed} land-use features`
                            : "unavailable"}
                      </p>
                      <details className="weather-details">
                        <summary>Sources, time & limits</summary>
                        <p>At {weather.latitude.toFixed(4)}, {weather.longitude.toFixed(4)} · Open-Meteo current conditions for {weather.current.time} UTC, retrieved {new Date(weather.retrieved_at).toLocaleString()}.</p>
                        <p>{weather.geography.note} Development counts are not population estimates. No mapped cover tags does not mean vegetation is absent.</p>
                        <p>This describes the observer location, not the fire location or historical photo-time weather. It does not change the detector score or produce a fire probability.</p>
                        <p><a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors</a> · Open-Meteo / Copernicus terrain.</p>
                        {weather.considerations.length > 0 && <p><b>Screening notes:</b> {weather.considerations.join(" ")}</p>}
                      </details>
                    </div>
                  )}
                  <label>
                    Operator notes
                    <textarea
                      maxLength="1000"
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      placeholder="Record uncertainty and the next action."
                    />
                  </label>
                  <div className="decision-buttons">
                  <button
                      className="primary"
                      disabled={busy || selected.status === "confirmed_fire"}
                      onClick={() => setConfirmFireOpen(true)}
                      title="Confirm this fire report; adding an affected-area point is optional."
                    >
                      {selected.status === "confirmed_fire" ? "Fire confirmed" : selectedIncidentPoint ? "Confirm fire & find nearby resources" : "Confirm fire"}
                    </button>
                    <button
                      className="primary"
                      disabled={busy}
                      onClick={() => review("escalated")}
                    >
                      Mark for escalation
                    </button>
                    <button disabled={busy} onClick={() => review("dismissed")}>
                      Dismiss
                    </button>
                  </div>
                  <p className="field-help">
                    Confirm only after independent human verification. The observer or camera position is not automatically treated as the fire location. This site does not notify authorities.
                  </p>
                  {selected.status === "confirmed_fire" && selectedIncidentPoint && (
                    <ResponseResources latitude={selectedIncidentPoint.latitude} longitude={selectedIncidentPoint.longitude} />
                  )}
                  {selected.kind === "thermal_observation" && !selectedIncidentPoint && <p className="field-help">Thermal pixel: {selected.latitude.toFixed(5)}, {selected.longitude.toFixed(5)} · {selected.thermal_observation?.source || "Satellite source"}. Add an affected-area point if you want map scenario and nearby-resource context.</p>}
                  {selected.review && (
                    <p>
                      Last decision:{" "}
                      {selected.review.decision.replaceAll("_", " ")} ·{" "}
                      {selected.review.notes || "No notes"}
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <div className="empty horizontal">
                <p>
                  Inspect the photo, model boxes, location, time, and satellite
                  evidence before recording a decision.
                </p>
              </div>
            )}
          </section>
          <div className={`audit-tool-stack ${activeTool === "audit" ? "workspace-tool-open" : ""}`}>
          <details className="activity panel">
            <summary>Report processing audit trail</summary>
            <div className="section-head">
              <h2>How this report was assessed</h2>
              <span>System processing · human decision</span>
            </div>
            <div className="stages">
              {["Intake", "Sentinel", "Correlator", "External reviewer", "Review"].map((name, i) => {
                const labels = ["Report received", "Photo screening", "Time & location check", "Optional second review", "Operator decision"];
                const done = (selected?.events || events).find(
                  (e) => e.agent === name,
                );
                return (
                  <div key={name}>
                    <span
                      className={
                        done &&
                        (name !== "Review" ||
                          (selected && selected.status !== "pending")) &&
                        (name !== "External reviewer" || !!selected?.external_opinion)
                          ? "done"
                          : ""
                      }
                    >
                      {i + 1}
                    </span>
                    <b>{labels[i]}</b>
                    <p>
                      {name === "Review" && selected?.review
                        ? `Operator decision recorded: ${selected.status.replaceAll("_", " ")}. No authority has been notified.`
                        : done?.message ||
                          [
                            "Receive observer report",
                            "Run trained YOLO detector",
                            "Compare time & proximity",
                            "Optional external vision check; runs only on operator request",
                            "Await operator assessment",
                          ][i]}
                    </p>
                  </div>
                );
              })}
            </div>
          </details>
          {selected ? (
            <Investigation
              report={selected}
              className={activeTool === "investigation" ? "workspace-tool-open" : ""}
              api={api}
              onReport={choose}
              onPacket={(packet) =>
                setInvestigationPacket(
                  packet ? { reportId: selected.id, data: packet } : null,
                )
              }
              onContext={setWeather}
              onRegionalEvidence={setFireContext}
              onShowCamera={() => setActiveTool("camera")}
            />
          ) : (
            <section
              className={`panel investigation ${activeTool === "investigation" ? "workspace-tool-open" : ""}`}
              id="investigation"
              aria-label="Wildfire investigation"
            >
              <div className="section-head">
                <div>
                  <span className="eyebrow">INVESTIGATION · EVIDENCE BEFORE ESCALATION</span>
                  <h2>Choose an observation to investigate</h2>
                </div>
              </div>
              <p>Select a report from the inbox to review its temporal evidence, nearby reports and cameras, public data, geographic context, and downloadable evidence packet.</p>
              <button onClick={() => setActiveTool("inbox")}>Open review inbox</button>
            </section>
          )}
          <details className="limitations panel">
            <summary>Coverage & assessment notes</summary>
            <p>
              Four Southern California cameras; one monitored feed at a time.
              Locations identify observers, not confirmed ignition points.
            </p>
            <p>
              Detections require human review. The model can miss smoke or flag
              lookalikes. Decisions are recorded here; emergency notifications
              and evacuation orders are not sent.
            </p>
          </details>
          </div>
        </main>
      )}
      <footer className="ww-footer">
        WildfireWatch · California wildfire evidence research
        <span>Local YOLO detector · runs on this server</span>
      </footer>
    </div>
  );
}
createRoot(document.getElementById("root")).render(
  <AppErrorBoundary>
    <OperatorGate>
      <App />
    </OperatorGate>
  </AppErrorBoundary>,
);
