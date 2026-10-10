import React, { useMemo, useState } from "react";

function sourceState(source, values, emptyLabel) {
  if (!source) return { state: "pending", label: "Not checked", detail: "Run this check to add current public context.", checked: "No request recorded" };
  const checkedAt = source.checked_at || source.refreshed_at || source.updated_at;
  const checked = checkedAt ? `Checked ${new Date(checkedAt).toLocaleString()}` : "Check time unavailable";
  if (source.status === "not_configured") return { state: "unavailable", label: "Access not configured", detail: source.limitations || "This source is not configured.", checked };
  if (source.status === "time_mismatch") return { state: "unavailable", label: "Outside time window", detail: source.limitations || "The source cannot be matched to this observation time.", checked };
  if (source.status !== "loaded") return { state: "unavailable", label: "Feed unavailable", detail: source.limitations || "The source did not return data.", checked };
  const count = values?.length || 0;
  return { state: count ? "found" : "clear", label: count ? `${count} result${count === 1 ? "" : "s"}` : emptyLabel, detail: source.limitations || "A search result is context, not confirmation.", checked };
}

export default function EvidenceNetwork({ report, packet, regional, context }) {
  const [active, setActive] = useState("report");
  const nodes = useMemo(() => {
    const firms = regional?.sources?.firms;
    const nifc = regional?.sources?.nifc;
    const nws = regional?.sources?.nws;
    const frames = packet?.video_evidence?.frames || packet?.temporal?.frames || [];
    const nearby = packet?.nearby_reports || [];
    const perimeter = sourceState(nifc, nifc?.features, "No current perimeter matched");
    const thermal = sourceState(firms, firms?.detections, "No thermal detections matched");
    const alerts = sourceState(nws, nws?.alerts, "No active alert matched");
    const geography = context
      ? { state: context.geography?.available ? "found" : "clear", label: context.geography?.available ? "Context loaded" : "Partial context", detail: `${context.elevation_m ?? "Unknown"} m elevation · ${context.current?.relative_humidity_2m ?? "—"}% humidity · ${context.current?.wind_speed_10m ?? "—"} ${context.units?.wind_speed_10m || "wind"}.` }
      : { state: "pending", label: "Not checked", detail: "Load weather and mapped landscape context for the observer position." };
    const external = report.external_opinion;
    return [
      { id: "camera", title: "Camera frames", tag: "SOURCE", position: [17, 20], state: frames.length ? "found" : "pending", label: frames.length ? `${frames.length} distinct frame${frames.length === 1 ? "" : "s"}` : "No sequence collected", detail: frames.length ? `Frame sequence available for a persistence check. Latest provider update ${frames[frames.length - 1]?.time || frames[frames.length - 1]?.timestamp || "time unavailable"}. Repeated frames do not independently establish a fire.` : "No camera sequence is available yet; this is missing evidence, not a negative detection." },
      { id: "thermal", title: "Satellite heat", tag: "NASA · FIRMS", position: [50, 10], ...thermal, detail: `${thermal.detail}${firms?.detections?.length ? ` ${firms.detections.length} thermal pixel(s) in the search window.` : ""} ${thermal.checked}` },
      { id: "perimeter", title: "Agency perimeters", tag: "NIFC · WFIGS", position: [83, 20], ...perimeter, detail: `${perimeter.detail}${nifc?.features?.length ? ` ${nifc.features.slice(0, 2).map((f) => `${f.name} · ${f.distance_km} km`).join("; ")}.` : ""} ${perimeter.checked}` },
      { id: "community", title: "Nearby reports", tag: "COMMUNITY", position: [17, 78], state: nearby.length ? "found" : "clear", label: nearby.length ? `${nearby.length} possible link${nearby.length === 1 ? "" : "s"}` : "No match found", detail: nearby.length ? nearby.slice(0, 2).map((r) => `${r.source} · ${r.distance_km} km · ${r.time_difference_hours} h apart`).join("; ") + ". Distance/time matches do not prove a shared incident." : "No report matched the current distance/time screen. Missing reports do not rule out a fire." },
      { id: "weather", title: "Weather alerts", tag: "NOAA · NWS", position: [83, 78], ...alerts, detail: `${alerts.detail}${nws?.alerts?.length ? ` ${nws.alerts.slice(0, 2).map((a) => `${a.event} · ${a.severity || "severity unavailable"}`).join("; ")}.` : ""} ${alerts.checked}` },
      { id: "landscape", title: "Weather & landscape", tag: "LOCAL CONTEXT", position: [35, 91], ...geography },
      { id: "review", title: "Second review", tag: "OPTIONAL", position: [65, 91], state: external ? "found" : "pending", label: external ? "Review recorded" : "Not requested", detail: external ? `${external.provider} · ${external.model}. ${external.limitations || "Uncalibrated model output; requires human interpretation."}` : "An external vision comparison is available only when configured and explicitly requested." },
      { id: "report", title: "Observation", tag: "REPORT", position: [50, 52], state: report.review ? "reviewed" : report.finding?.smoke_detected ? "flagged" : "screened", label: report.review ? report.review.decision.replaceAll("_", " ") : report.finding?.smoke_detected ? "Candidate · review needed" : "Screened · no candidate", detail: `${report.source || "Submitted observation"} · ${new Date(report.observed_at).toLocaleString()}${report.finding?.confidence != null ? ` · ${Math.round(report.finding.confidence * 100)}% uncalibrated model score` : ""}. Observer location is not confirmed ignition location.` },
    ];
  }, [report, packet, regional, context]);
  const selected = nodes.find((node) => node.id === active) || nodes[nodes.length - 1];
  const edges = ["camera", "thermal", "perimeter", "community", "weather", "landscape", "review"].map((id) => [id, "report"]);
  const jumpTo = (selector) => document.querySelector(selector)?.scrollIntoView({ behavior: "smooth", block: "center" });

  return (
    <section className="evidence-network" aria-labelledby="evidence-network-title">
      <div className="evidence-network-heading">
        <div>
          <span className="eyebrow">CASE CONNECTIONS</span>
          <h3 id="evidence-network-title">One observation. Every relevant signal.</h3>
          <p>See what supports a review, what is still unknown, and where each result came from.</p>
        </div>
        <span className="network-count">{nodes.filter((n) => ["found", "clear", "screened", "flagged", "reviewed"].includes(n.state)).length} of {nodes.length} checks with a result</span>
      </div>
      <div className="evidence-network-body">
        <div className="network-canvas" role="group" aria-label="Evidence relationships for this observation">
          <svg className="network-lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            {edges.map(([id, target]) => {
              const a = nodes.find((n) => n.id === id).position;
              const b = nodes.find((n) => n.id === target).position;
              return <line key={id} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} className={active === id || active === target ? "is-active" : ""} />;
            })}
          </svg>
          {nodes.map((node) => (
            <button key={node.id} className={`network-node state-${node.state} ${node.id === "report" ? "is-report" : ""} ${active === node.id ? "is-selected" : ""}`} style={{ left: `${node.position[0]}%`, top: `${node.position[1]}%` }} onClick={() => setActive(node.id)} aria-pressed={active === node.id}>
              <span className="network-node-tag">{node.tag}</span>
              <b>{node.title}</b>
              <small>{node.label}</small>
            </button>
          ))}
        </div>
        <aside className="network-inspector" aria-live="polite">
          <span className={`network-state state-${selected.state}`}>{selected.label}</span>
          <h4>{selected.title}</h4>
          <p>{selected.detail}</p>
          <small>{selected.tag} · {selected.id === "report" ? "Original report record" : selected.id === "community" ? "Distance / time association · no match is not no fire" : selected.id === "camera" ? "Camera sequence" : selected.id === "landscape" ? "Observer position context" : "Public-source check · age shown when provider supplies a timestamp"}</small>
          {selected.id === "camera" && <button className="network-action" onClick={() => jumpTo(".camera-panel")}>Open camera monitoring ↓</button>}
          {selected.id === "landscape" && !context && <button className="network-action" onClick={() => jumpTo(".geography-action")}>Load location context ↓</button>}
          {["thermal", "perimeter", "weather"].includes(selected.id) && !regional && <button className="network-action" onClick={() => jumpTo("#regional-evidence")}>Check public records ↓</button>}
          {selected.id === "community" && <button className="network-action" onClick={() => jumpTo(".community-evidence")}>Review nearby reports ↓</button>}
        </aside>
      </div>
      <p className="network-caveat">Connections organize review context; they do not prove that reports describe the same fire, identify ignition, or create an evacuation order.</p>
    </section>
  );
}
