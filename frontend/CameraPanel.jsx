import React, { useEffect, useState } from "react";

export default function CameraPanel({ available, api, onReport, className = "" }) {
  const [camera, setCamera] = useState(null);
  const [sequence, setSequence] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let stopped = false;
    async function refresh() {
      if (!available) return;
      try {
        const result = await api("/api/camera");
        if (!stopped) {
          setCamera(result);
          setError("");
        }
      } catch {
        if (!stopped)
          setError("Live camera service unavailable in this installation.");
      }
    }
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [available]);
  useEffect(() => {
    let cancelled = false;
    setSequence([]);
    if (available && camera?.latest)
      api("/api/camera/sequence")
        .then((result) => {
          if (!cancelled && result.camera_id === camera.camera.id)
            setSequence(result.frames);
        })
        .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [available, camera?.camera?.id, camera?.latest?.provider_updated_at]);
  async function action(name, body = {}) {
    setBusy(true);
    setError("");
    try {
      setCamera(await api(`/api/camera/${name}`, body));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const latest = camera?.latest;
  const finding = latest?.finding;
  const age = latest
    ? Math.max(0, (Date.now() - new Date(latest.provider_updated_at)) / 60000)
    : null;
  return (
    <section className={`camera-panel panel ${className}`} aria-label="Live camera monitoring">
      <div className="section-head">
        <div>
          <span className="eyebrow">01 · Observe</span>
          <h2>Live camera monitoring</h2>
          <p>
            {camera?.camera?.name ||
              "Choose a Southern California research camera"}
          </p>
        </div>
        <span className={camera?.running ? "camera-running" : ""}>
          {camera?.running
            ? "Monitoring · every 60 seconds"
            : "Monitoring stopped"}
        </span>
      </div>
      <div className="camera-selection">
        <label htmlFor="camera-source">Camera source</label>
        <select
          id="camera-source"
          value={camera?.camera?.id || "pi-e-mobo-c"}
          disabled={!available || busy || !camera?.cameras}
          onChange={(e) => action("select", { camera_id: e.target.value })}
        >
          {(
            camera?.cameras || [
              {
                id: "pi-e-mobo-c",
                name: "Los Pinos East · connect backend to choose feeds",
              },
            ]
          ).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <span>Detector: our trained YOLO11n</span>
      </div>
      <div className="camera-body">
        <div>
          {latest ? (
            <div className="camera-photo">
              <img
                src={latest.image}
                alt={`Unmodified HPWREN ${camera?.camera?.name || "camera"} image with provider timestamp and credit`}
              />
              {(finding?.boxes || [])
                .filter((b) => b.score >= 0.25)
                .map((b, i) => {
                  const [x, y, r, bottom] = b.xyxy_normalized;
                  return (
                    <span
                      key={i}
                      className="camera-box"
                      style={{
                        left: `${x * 100}%`,
                        top: `${y * 100}%`,
                        width: `${(r - x) * 100}%`,
                        height: `${(bottom - y) * 100}%`,
                      }}
                    >
                      <span className="sr-only">
                        Smoke candidate {Math.round(b.score * 100)}%
                      </span>
                    </span>
                  );
                })}
            </div>
          ) : (
            <div className="camera-empty">
              Fetch a current image to run real YOLO inference. No API key
              needed.
            </div>
          )}
          <small>
            Image:{" "}
            <a
              href="https://www.hpwren.ucsd.edu/cameras/"
              target="_blank"
              rel="noreferrer"
            >
              HPWREN · UC San Diego · NSF / ALERTCalifornia
            </a>
            . Original timestamp and credits preserved.{" "}
            <a
              href="https://www.hpwren.ucsd.edu/cc.html"
              target="_blank"
              rel="noreferrer"
            >
              Noncommercial research use conditions
            </a>
            .
          </small>
        </div>
        <div className="camera-controls">
          <div className="camera-actions">
            <button
              disabled={busy || !available}
              onClick={() => action("sample")}
            >
              Analyze current frame
            </button>
            <button
              className="primary"
              disabled={busy || !available}
              onClick={() => action(camera?.running ? "stop" : "start")}
            >
              {camera?.running
                ? "Stop live monitoring"
                : "Start live monitoring"}
            </button>
          </div>
          <p role="status">
            {busy
              ? "Fetching / analyzing…"
              : error ||
                camera?.message ||
                "Connect the backend to enable live monitoring."}
          </p>
          {latest && (
            <>
              <h3>
                {finding.smoke_detected
                  ? "Smoke candidate · human review needed"
                  : "No smoke above model threshold"}
              </h3>
              <p>
                Uncalibrated score {Math.round(finding.confidence * 100)}% ·
                threshold 25%
              </p>
              <dl>
                <dt>Provider image update</dt>
                <dd>{new Date(latest.provider_updated_at).toLocaleString()}</dd>
                <dt>Fetched / analyzed</dt>
                <dd>{new Date(latest.fetched_at).toLocaleString()}</dd>
                <dt>Image age now</dt>
                <dd>
                  {age.toFixed(1)} minutes{" "}
                  {age > 5 ? "· OLD IMAGE, not current" : ""}
                </dd>
                <dt>Camera position</dt>
                <dd>
                  {camera?.camera?.latitude?.toFixed(5)},{" "}
                  {camera?.camera?.longitude?.toFixed(5)} · facing east
                </dd>
              </dl>
              {latest.report_id && (
                <button onClick={() => onReport(latest.report_id)}>
                  Open smoke candidate in inbox
                </button>
              )}
            </>
          )}
          <p className="camera-note">
            One selected feed at a time; four Southern California cameras, not
            statewide coverage. Changing cameras stops monitoring. Provider
            update time is not verified capture time. New images only; stale
            images rejected. Smoke candidates enter the inbox at most once per
            five minutes. No emergency alert is sent.
          </p>
        </div>
      </div>
      {!!sequence.length && (
        <details className="frame-sequence">
          <summary>Compare recent frames ({sequence.length})</summary>
          <p>
            Unmodified snapshots. Provider update time is not verified capture
            time. Six frames maximum; changing cameras clears this sequence.
          </p>
          <div className="sequence-grid">
            {[...sequence].reverse().map((f) => (
              <figure key={f.provider_updated_at}>
                <img
                  src={f.image}
                  alt={`Camera frame updated ${f.provider_updated_at}`}
                />
                <figcaption>
                  {new Date(f.provider_updated_at).toLocaleTimeString()} · score{" "}
                  {Math.round(f.finding.confidence * 100)}% ·{" "}
                  {f.finding.smoke_detected ? "candidate" : "below threshold"}
                </figcaption>
              </figure>
            ))}
          </div>
          {camera.temporal &&
            [
              ...camera.temporal.support,
              ...camera.temporal.against,
              ...camera.temporal.unknown,
            ].map((s, i) => <p key={i}>{s}</p>)}
        </details>
      )}
      {!!camera?.history?.length && (
        <details className="camera-history">
          <summary>Recent checks ({camera.history.length})</summary>
          <ol>
            {camera.history.map((h, i) => (
              <li key={i}>
                {new Date(h.fetched_at || h.checked_at).toLocaleTimeString()} ·{" "}
                {h.outcome ||
                  (h.finding?.smoke_detected
                    ? "Smoke candidate"
                    : "No smoke above threshold")}{" "}
                {h.finding &&
                  `· score ${Math.round(h.finding.confidence * 100)}%`}{" "}
                {h.report_id && "· added to inbox"}
                {h.message && ` · ${h.message}`}
              </li>
            ))}
          </ol>
        </details>
      )}
    </section>
  );
}
