import React, { useEffect, useState } from "react";
export default function Investigation({ report, api, onReport, onPacket, onContext, onRegionalEvidence, onShowCamera, className = "" }) {
  const [packet, setPacket] = useState(null),
    [error, setError] = useState(""),
    [refreshError, setRefreshError] = useState(""),
    [busy, setBusy] = useState(false),
    [context, setContext] = useState(null),
    [regional, setRegional] = useState(null);
  useEffect(() => {
    let cancelled = false;
    setPacket(null);
    onPacket?.(null);
    setContext(null);
    setRegional(null);
    onRegionalEvidence?.(null);
    setError("");
    setRefreshError("");
    async function refresh() {
      try {
        const p = await api(`/api/reports/${report.id}/investigation`);
        if (!cancelled) {
          setPacket(p);
          onPacket?.(p);
          setRefreshError("");
        }
      } catch (e) {
        if (!cancelled) setRefreshError(e.message);
      }
    }
    refresh();
    const timer = setInterval(refresh, 10000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [report.id]);
  async function geography() {
    setBusy(true);
    try {
      const result = await api(
        `/api/location-context?latitude=${report.latitude}&longitude=${report.longitude}`,
      );
      setContext(result);
      onContext?.(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function loadRegionalEvidence() {
    setBusy(true);
    setError("");
    try {
      const result = await api(`/api/reports/${report.id}/regional-evidence`);
      setRegional(result);
      onRegionalEvidence?.({ reportId: report.id, data: result });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function inspect(id) {
    setBusy(true);
    try {
      await api("/api/camera/select", { camera_id: id });
      await api("/api/camera/sample", {});
      setError(
        "Camera selected and one frame requested. Use Live camera monitoring to inspect the image and start continued monitoring.",
      );
      onShowCamera?.();
      document
        .querySelector(".camera-panel")
        ?.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function download() {
    setBusy(true);
    try {
      const complete = await api(
        `/api/reports/${report.id}/investigation?include_image=true`,
      );
      const b = new Blob(
        [
          JSON.stringify(
            {
              ...complete,
              geographic_context: context,
              exported_at: new Date().toISOString(),
            },
            null,
            2,
          ),
        ],
        { type: "application/json" },
      );
      const u = URL.createObjectURL(b);
      const a = document.createElement("a");
      a.href = u;
      a.download = `wildfirewatch-${report.id}-evidence.json`;
      a.click();
      URL.revokeObjectURL(u);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className={`panel investigation ${className}`}
      id="investigation"
      aria-label="Wildfire investigation"
    >
      <div className="section-head">
        <div>
          <span className="eyebrow">
            Investigate · evidence before escalation
          </span>
          <h2>Is this smoke? What should we check next?</h2>
        </div>
        <button disabled={!packet || busy} onClick={download}>
          Download evidence packet
        </button>
      </div>
      {error && <p role="status">{error}</p>}
      {refreshError && (
        <p role="status">
          Evidence refresh unavailable.{" "}
          {packet
            ? "Showing the last received assessment."
            : "Retrying automatically…"}
        </p>
      )}
      {!packet ? (
        <p>Loading evidence assessment…</p>
      ) : (
        <>
          <div className="investigation-columns">
            {[
              ["Supporting evidence", packet.support],
              ["Evidence that weakens suspicion", packet.against],
              ["Unresolved questions", packet.unknown],
            ].map(([title, items]) => (
              <div key={title}>
                <h3>{title}</h3>
                <ul>
                  {(items.length
                    ? items
                    : ["No evidence recorded in this category."]
                  ).map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <h3>
            {packet.video_evidence
              ? "Video evidence · sampled frame findings"
              : "Temporal evidence · distinct camera frames"}
          </h3>
          {packet.video_evidence ? (
            <div className="temporal-table">
              <table>
                <thead>
                  <tr>
                    <th>Time in clip</th>
                    <th>Model score</th>
                    <th>Finding</th>
                    <th>Candidate regions</th>
                  </tr>
                </thead>
                <tbody>
                  {packet.video_evidence.frames.map((frame) => (
                    <tr key={frame.offset_seconds}>
                      <td>{frame.offset_seconds.toFixed(1)}s</td>
                      <td>
                        {Math.round(frame.confidence * 100)}% · uncalibrated
                      </td>
                      <td>
                        {frame.smoke_detected
                          ? "Possible smoke"
                          : "Below threshold"}
                      </td>
                      <td>{frame.boxes.length}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : packet.temporal.frames.length ? (
            <div className="temporal-table">
              <table>
                <thead>
                  <tr>
                    <th>Provider update</th>
                    <th>Model score</th>
                    <th>Candidate</th>
                    <th>Largest box / image area</th>
                  </tr>
                </thead>
                <tbody>
                  {packet.temporal.frames.map((f) => (
                    <tr key={f.time}>
                      <td>{new Date(f.time).toLocaleTimeString()}</td>
                      <td>{Math.round(f.score * 100)}%</td>
                      <td>
                        {f.candidate ? "Above threshold" : "Below threshold"}
                      </td>
                      <td>{(f.area * 100).toFixed(3)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p>
              Sequence unavailable. Collect another camera frame to check
              persistence.
            </p>
          )}
          <p className="field-help">
            {packet.video_evidence
              ? `${packet.video_evidence.sampling_note} Smoke candidates do not confirm a fire.`
              : "Persistence alone does not confirm smoke. Scores are not fire probabilities."}
          </p>
          <div className="community-evidence">
            <div>
              <span className="eyebrow">COMMUNITY OBSERVATIONS</span>
              <h3>Other observations nearby</h3>
            </div>
            {packet.nearby_reports?.length ? (
              <>
                <p>
                  {packet.nearby_reports.length} report(s) match the 25 km / 24
                  hour screen. These may be useful independent observations; an
                  operator must verify source and event.
                </p>
                <div className="nearby-report-list">
                  {packet.nearby_reports.map((item) => (
                    <button
                      key={item.id}
                      className="nearby-report"
                      onClick={() => onReport?.(item.id)}
                    >
                      <span>
                        <b>{item.source}</b>
                        <small>
                          {new Date(item.observed_at).toLocaleString()} ·{" "}
                          {item.distance_km} km · {item.time_difference_hours} h
                          apart
                        </small>
                      </span>
                      <span className="nearby-finding">
                        {item.finding.smoke_detected
                          ? "Smoke candidate"
                          : "Below threshold"}{" "}
                        · {Math.round(item.finding.confidence * 100)}%
                      </span>
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <p>
                No separate report matched this time and distance screen. No
                match does not rule out a fire.
              </p>
            )}
            <small>
              Distance/time matches do not prove the reports describe the same
              event or locate an ignition.
            </small>
          </div>
          <section className="signal-convergence" id="regional-evidence" aria-labelledby="signal-convergence-title">
            <div className="signal-convergence-head">
              <div>
                <span className="eyebrow">PUBLIC DATA CHECK</span>
                <h3 id="signal-convergence-title">Check nearby public records</h3>
                <p>Look for satellite heat detections, agency perimeters and weather alerts near the observer position.</p>
              </div>
              <button className="primary" disabled={busy || packet.reference} onClick={loadRegionalEvidence}>
                {busy ? "Checking public feeds…" : regional ? "Refresh regional signals" : "Check regional signals"}
              </button>
            </div>
            {packet.reference && <p className="field-help">Live geographic checks are disabled because this media uses reference coordinates rather than a verified capture location.</p>}
            {!regional ? (
              <div className="signal-empty">No regional sources have been queried for this observation yet.</div>
            ) : (
              <>
                <div className="signal-grid">
                  <article className="signal-card">
                    <span className="signal-source">NASA · VIIRS thermal</span>
                    <b>{regional.sources.firms.status === "loaded" ? `${regional.sources.firms.detections.length} thermal pixels · 25 km / 24 h` : regional.sources.firms.status === "not_configured" ? "Access not configured" : regional.sources.firms.status === "time_mismatch" ? "Observation too old" : "Feed unavailable"}</b>
                    {regional.sources.firms.detections.slice(0, 3).map((item, i) => <small key={i}>{item.distance_km} km · {item.hours_from_observation} h from report · {item.confidence || "confidence unknown"}</small>)}
                    <small>{regional.sources.firms.limitations}</small>
                    {regional.sources.firms.status === "not_configured" && <small>Live NASA FIRMS checks require a free FIRMS_MAP_KEY in the backend environment. Restart the backend after configuring it.</small>}
                    {regional.sources.firms.status === "not_configured" && <a href="https://firms.modaps.eosdis.nasa.gov/api/map_key/" target="_blank" rel="noreferrer">Get a free NASA MAP_KEY ↗</a>}
                    <a href="https://firms.modaps.eosdis.nasa.gov/" target="_blank" rel="noreferrer">NASA FIRMS source ↗</a>
                  </article>
                  <article className="signal-card">
                    <span className="signal-source">NIFC · WFIGS perimeter</span>
                    <b>{regional.sources.nifc.status === "loaded" ? `${regional.sources.nifc.features.length} current perimeters within 75 km` : "Feed unavailable"}</b>
                    {regional.sources.nifc.features.slice(0, 3).map((item, i) => <small key={i}>{item.name} · {item.distance_km} km from observer{item.acres ? ` · ${Math.round(item.acres).toLocaleString()} mapped acres` : ""} · perimeter update {item.last_updated ? new Date(item.last_updated).toLocaleString() : "time unavailable"}</small>)}
                    {!regional.sources.nifc.features.length && regional.sources.nifc.status === "loaded" && <small>No public current perimeter found in the search radius; not evidence that no fire exists.</small>}
                    <small>{regional.sources.nifc.limitations}</small>
                    <a href="https://data-nifc.opendata.arcgis.com/" target="_blank" rel="noreferrer">NIFC WFIGS source ↗</a>
                  </article>
                  <article className="signal-card">
                    <span className="signal-source">NOAA · NWS active alerts</span>
                    <b>{regional.sources.nws.status === "loaded" ? `${regional.sources.nws.alerts.length} relevant active alerts` : "Feed unavailable"}</b>
                    {regional.sources.nws.alerts.slice(0, 3).map((item, i) => <small key={i}>{item.event} · {item.severity || "severity unavailable"}{item.expires ? ` · through ${new Date(item.expires).toLocaleString()}` : ""}</small>)}
                    {!regional.sources.nws.alerts.length && regional.sources.nws.status === "loaded" && <small>No matching active alert at this coordinate; absence of an alert does not rule out fire.</small>}
                    <small>{regional.sources.nws.limitations}</small>
                    <a href="https://www.weather.gov/documentation/services-web-api" target="_blank" rel="noreferrer">NWS API source ↗</a>
                  </article>
                </div>
                <div className="signal-readout">
                  <b>Evidence is aligned by source, distance and time—not collapsed into a confidence score.</b>
                  <span>{regional.interpretation} Checked {new Date(regional.generated_at).toLocaleString()}.</span>
                </div>
              </>
            )}
          </section>
          <h3>Next useful observations</h3>
          <ol>
            {packet.next_steps.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ol>
          <p>
            Cameras nearest the observer · plume visibility unverified.
            Switching stops the current feed.
          </p>
          <div className="next-cameras">
            {packet.nearby_cameras.slice(0, 3).map((c) => (
              <button key={c.id} disabled={busy} onClick={() => inspect(c.id)}>
                Inspect {c.name} · {c.distance_km} km
              </button>
            ))}
          </div>
          <button className="geography-action" disabled={busy || packet.reference} onClick={geography}>
            Gather geographic context for evidence packet
          </button>
          {context && (
            <p role="status">
              Context attached: elevation {context.elevation_m ?? "unknown"} m ·
              humidity {context.current.relative_humidity_2m}% · wind{" "}
              {context.current.wind_speed_10m} {context.units.wind_speed_10m}.
              Vegetation / development{" "}
              {context.geography.available ? "loaded" : "unavailable"}.{" "}
              {context.considerations.join(" ")}
            </p>
          )}
          <p className="field-help">
            Export includes evidence, sources and the recorded decision.
            Authorities are not notified.
          </p>
        </>
      )}
    </section>
  );
}
