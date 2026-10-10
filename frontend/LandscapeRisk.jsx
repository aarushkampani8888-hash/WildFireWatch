import React, { useEffect, useState } from "react";

async function request(path, body) {
  const response = await fetch(path, body ? {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  } : {});
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw Error(data.detail || "Landscape assessment is unavailable.");
  return data;
}

export default function LandscapeRisk({ point, onUseAsIncidentLocation, onAssessment, className = "" }) {
  const [assessment, setAssessment] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [brief, setBrief] = useState(null);
  useEffect(() => {
    if (!point) return;
    const controller = new AbortController();
    setLoading(true);
    setAssessment(null);
    onAssessment?.(null);
    setBrief(null);
    setError("");
    const query = new URLSearchParams({
      latitude: point.latitude,
      longitude: point.longitude,
    });
    fetch(`/api/landscape-risk?${query}`, { signal: controller.signal })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw Error(data.detail || "Landscape assessment is unavailable.");
        setAssessment(data);
        onAssessment?.(data);
      })
      .catch((e) => { if (e.name !== "AbortError") setError(e.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [point?.latitude, point?.longitude, onAssessment]);

  async function generateBrief() {
    if (!point) return;
    setAiLoading(true);
    setError("");
    try {
      setBrief(await request("/api/landscape-risk/ai-brief", point));
    } catch (e) { setError(e.message); }
    finally { setAiLoading(false); }
  }

  return (
    <section className={`panel landscape-risk ${className}`} aria-live="polite">
      <div className="section-head">
        <div>
          <span className="eyebrow">California-only terrain inspection</span>
          <h2>Landscape fire-risk screening</h2>
        </div>
        {assessment && <span>{assessment.location.latitude.toFixed(4)}, {assessment.location.longitude.toFixed(4)}</span>}
      </div>
      <div className="landscape-risk-content">
        {!point && <p>Click any point on the map to inspect California terrain, vegetation context, current weather and public alerts.</p>}
        {loading && <p role="status">Checking California boundary and loading public terrain, land-cover and weather data…</p>}
        {error && <p className="landscape-error" role="alert">{error}</p>}
        {assessment && <>
          <div className="landscape-score">
            <div><span className="eyebrow">Environmental conditions index</span><strong>{assessment.screening.index == null ? "—" : `${assessment.screening.index}/100`}</strong><span>{assessment.screening.label} · {assessment.screening.coverage_percent}% factor coverage</span></div>
            <p>This is a transparent, uncalibrated conditions screen—not the probability of ignition, an official fire-danger rating, or detector confidence.</p>
          </div>
          <div className="landscape-facts">
            <div><b>Terrain</b><span>{assessment.terrain.elevation_m == null ? "Unavailable" : `${assessment.terrain.elevation_m} m elevation`}</span><span>{assessment.terrain.slope_degrees == null ? "Slope unavailable" : `${assessment.terrain.slope_degrees}° slope`}</span></div>
            <div><b>Mapped context</b><span>{assessment.landscape?.cover?.length ? assessment.landscape.cover.join(", ") : "No vegetation tags returned"}</span><span>{assessment.landscape?.roads_within_2km ?? "—"} mapped road features within 2 km</span></div>
            <div><b>Active NWS alerts</b><span>{assessment.alerts == null ? "Feed unavailable" : assessment.alerts.length ? assessment.alerts.map((a) => a.event).join(", ") : "No matching alert"}</span></div>
          </div>
          {onUseAsIncidentLocation && <button className="primary" onClick={() => onUseAsIncidentLocation(point)}>Use this point as the affected area</button>}
          {onUseAsIncidentLocation && <p className="field-help">Adding an approximate affected-area point is optional. You can confirm an early warning before any area has been mapped.</p>}
          <div className="landscape-factors"><h3>What contributes to this index</h3>{assessment.screening.factors.map((factor) => <div key={factor.name} className="landscape-factor"><div><b>{factor.name}</b><span>{factor.available ? `${factor.value} · ${factor.points}/${factor.maximum} points` : "Unavailable · not inferred"}</span></div><p>{factor.note}</p></div>)}</div>
          {assessment.screening.ai_summary_available && <button disabled={aiLoading} onClick={generateBrief}>{aiLoading ? "Writing evidence brief…" : "Generate AI evidence brief"}</button>}
          {brief && <div className="landscape-brief"><b>AI evidence brief</b><p>{brief.brief}</p>{brief.watch_items?.length > 0 && <p><b>Watch items:</b> {brief.watch_items.join(" · ")}</p>}{brief.missing_evidence?.length > 0 && <p><b>Missing evidence:</b> {brief.missing_evidence.join(" · ")}</p>}<small>{brief.note}</small></div>}
          <details><summary>Sources and limitations</summary><p>{Object.entries(assessment.sources).filter(([, value]) => value).map(([name, value]) => `${name}: ${value}`).join(" · ")}</p><ul>{assessment.limitations.map((item) => <li key={item}>{item}</li>)}</ul><p>{assessment.terrain.resolution_note} {assessment.screening.method}</p><p>For longer-term context, compare this point with the <a href="https://www.fire.ca.gov/osfm/what-we-do/community-wildfire-preparedness-and-mitigation/fire-hazard-severity-zones" target="_blank" rel="noreferrer">CAL FIRE hazard-severity zones</a> (fuels, terrain and typical fire weather; not a live forecast) and the <a href="https://www.drought.gov/data-maps-tools/us-drought-monitor" target="_blank" rel="noreferrer">U.S. Drought Monitor</a> (updated weekly; not a measurement of local fuel moisture).</p></details>
        </>}
      </div>
    </section>
  );
}
