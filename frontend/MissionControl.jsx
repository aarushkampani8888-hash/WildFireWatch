import React, { useEffect, useState } from "react";
export default function MissionControl({
  api,
  available,
  onReview,
  onSubmit,
  onNetwork,
}) {
  const [mission, setMission] = useState(null),
    [error, setError] = useState(""),
    [climate, setClimate] = useState(null),
    [climateState, setClimateState] = useState("loading");
  useEffect(() => {
    let cancelled = false;
    async function refresh() {
      if (!available) return;
      try {
        const m = await api("/api/mission");
        if (!cancelled) {
          setMission(m);
          onNetwork?.(m);
          setError("");
        }
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    }
    refresh();
    const t = setInterval(refresh, 15000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [available]);
  useEffect(() => {
    let cancelled = false;
    const station = mission?.camera;
    if (!available || !station?.latitude || !station?.longitude) return;
    setClimate(null);
    setClimateState("loading");
    api(
      `/api/location-context?latitude=${station.latitude}&longitude=${station.longitude}`,
    )
      .then((value) => {
        if (!cancelled) {
          setClimate(value);
          setClimateState("ready");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setClimate(null);
          setClimateState("unavailable");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [
    available,
    mission?.camera?.id,
    mission?.camera?.latitude,
    mission?.camera?.longitude,
  ]);
  const top = mission?.queue?.[0];
  return (
    <section className="mission-control" aria-label="Operator action center">
      <div className="mission-intro">
        <div>
          <span className="eyebrow">WILDFIRE EVIDENCE · HUMAN DECISIONS</span>
          <h2>
            Turn early signals
            <br />
            into shared evidence.
          </h2>
          <p>
            A wildfire-readiness workspace for forestry and local response
            teams: screen public cameras, connect community observations,
            understand current conditions, and keep the final decision with a
            person.
          </p>
        </div>
        <div className="mission-actions">
          <button onClick={onSubmit}>＋ Add community observation</button>
          <button
            onClick={() =>
              document
                .querySelector(".camera-panel")
                ?.scrollIntoView({ behavior: "smooth" })
            }
          >
            View monitoring station →
          </button>
        </div>
      </div>
      <div className="mission-metrics">
        <div>
          <strong>{mission?.queue.length ?? "—"}</strong>
          <span>Reports awaiting review</span>
        </div>
        <div>
          <strong>{mission?.camera.distinct_frames ?? "—"}</strong>
          <span>Distinct frames from selected camera</span>
        </div>
        <div>
          <strong>{mission?.nearby_report_matches ?? "—"}</strong>
          <span>Possible nearby report links</span>
        </div>
        <div>
          <strong>{mission?.camera.running ? "LIVE" : "READY"}</strong>
          <span>{mission?.camera.name || "Selected camera"}</span>
        </div>
      </div>
      <section
        className="response-path"
        aria-label="Wildfire evidence workflow"
      >
        <div className="response-path-heading">
          <span className="eyebrow">
            FROM SIGNAL TO COMMUNITY-READY DECISION
          </span>
          <p>
            One auditable path for evidence that usually arrives in separate
            places.
          </p>
        </div>
        <div className="response-path-steps">
          {[
            ["01", "Observe", "Public camera frames + resident reports"],
            [
              "02",
              "Screen",
              "Local YOLO smoke candidates; preserve the source image",
            ],
            [
              "03",
              "Corroborate",
              "Distinct frames, nearby reports, weather + thermal context",
            ],
            [
              "04",
              "Decide",
              "Operator records a reasoned action and evidence packet",
            ],
          ].map(([number, title, detail], index) => (
            <div className="response-step" key={number}>
              <span className="response-step-number">{number}</span>
              <div>
                <b>{title}</b>
                <small>{detail}</small>
              </div>
              {index < 3 && (
                <span className="response-step-arrow" aria-hidden="true">
                  →
                </span>
              )}
            </div>
          ))}
        </div>
        <small className="response-path-note">
          The original image, timestamp, model finding, corroboration and
          unknowns travel together. Screening is not confirmation; no automatic
          public alert is sent.
        </small>
        <details className="model-proof">
          <summary>Model evaluation and limits</summary>
          <div className="model-proof-results">
            <b>76.8% smoke-presence recall</b>
            <b>53.1% on camera-disjoint Pyro-SDIS images</b>
            <b>4.9% image false-positive rate at 0.25 threshold</b>
            <small>Held-out 5,240-image test · image-level metrics · uncalibrated · not validated for emergency response</small>
          </div>
        </details>
      </section>
      <section
        className="climate-context"
        aria-label="Current conditions at selected monitoring station"
      >
        <div className="climate-context-copy">
          <span className="eyebrow">
            CLIMATE CONDITIONS · MONITORING STATION
          </span>
          <h3>{mission?.camera.name || "Selected station"}</h3>
          <p>
            Live weather and mapped land-cover context help operators understand
            the environment around a camera before interpreting a signal.
          </p>
          <small>
            Station coordinates are not the fire location, and a camera view may
            extend beyond this 2 km buffer. Current conditions are not the
            conditions at an older image’s capture time.
          </small>
        </div>
        {climate ? (
          <div className="climate-readout">
            <div
              className="wind-dial"
              aria-label={`Wind from ${climate.current.wind_direction_10m} degrees`}
            >
              <span>N</span>
              <span>E</span>
              <span>S</span>
              <span>W</span>
              <i
                style={{
                  transform: `rotate(${climate.current.wind_direction_10m}deg)`,
                }}
              />
              <b>{climate.current.wind_direction_10m}°</b>
            </div>
            <div className="climate-values">
              <div>
                <strong>{climate.current.wind_speed_10m}</strong>
                <span>
                  {climate.units.wind_speed_10m} wind · from{" "}
                  {climate.current.wind_direction_10m}°
                </span>
              </div>
              <div>
                <strong>{climate.current.relative_humidity_2m}%</strong>
                <span>relative humidity</span>
              </div>
              <div>
                <strong>{climate.current.temperature_2m}°</strong>
                <span>air temperature</span>
              </div>
              <div>
                <strong>{climate.elevation_m ?? "—"} m</strong>
                <span>terrain elevation</span>
              </div>
            </div>
            <div className="climate-map-context">
              <b>Landscape within 2 km of the station</b>
              <span>
                {climate.geography.available
                  ? `${climate.geography.buildings} mapped buildings · ${climate.geography.developed} developed land-use features · ${climate.geography.water} water features`
                  : "Map features unavailable; no absence inferred."}
              </span>
              <span>
                Mapped cover:{" "}
                {climate.geography.available
                  ? climate.geography.cover.join(", ") ||
                    "no tagged vegetation returned"
                  : "unavailable"}
                . Counts are mapped features, not people, area, or fuel load.
              </span>
              <b>Environmental review prompts · not a risk score</b>
              {climate.considerations.map((item) => (
                <span key={item}>• {item}</span>
              ))}
            </div>
            <small className="climate-attribution">
              Open-Meteo current conditions · © OpenStreetMap contributors ·
              updated {new Date(climate.retrieved_at).toLocaleTimeString()}
            </small>
          </div>
        ) : (
          <div className="climate-unavailable" role="status">
            {climateState === "loading"
              ? "Loading current station conditions…"
              : "Live weather or mapped geography is unavailable. No simulated values substituted."}
          </div>
        )}
      </section>
      {error && <p role="status">Action center unavailable: {error}</p>}
      <div className="mission-work">
        <div className="next-decision">
          <span className="eyebrow">NEXT OPERATOR ACTION</span>
          <h3>
            {top ? top.location : "Collect the first independent observation"}
          </h3>
          <p>
            {top
              ? top.action
              : "Monitor a camera or accept a community photo. A clear scene is useful evidence; do not wait for a high model score to start reviewing."}
          </p>
          {top ? (
            <>
              <p className="mission-time">
                Observed {new Date(top.observed_at).toLocaleString()} ·{" "}
                {top.status.replaceAll("_", " ")} ·{" "}
                {Math.round(top.score * 100)}% uncalibrated model score
              </p>
              <div className="evidence-steps">
                {Object.entries(top.evidence_checks).map(([name, done]) => (
                  <span className={done ? "checked" : "missing"} key={name}>
                    {done ? "✓" : "○"} {name.replaceAll("_", " ")}
                  </span>
                ))}
              </div>
              {top.nearby_reports?.length > 0 && (
                <div className="linked-observations">
                  <b>Possible nearby observations</b>
                  {top.nearby_reports.slice(0, 2).map((r) => (
                    <button key={r.id} onClick={() => onReview(r.id)}>
                      Compare {r.source} · {r.distance_km} km ·{" "}
                      {r.time_difference_hours} h
                    </button>
                  ))}
                  <small>
                    Time and distance match only; verify the source and event.
                  </small>
                </div>
              )}
              <button
                onClick={() => {
                  onReview(top.id);
                  setTimeout(
                    () =>
                      document
                        .querySelector(".evidence-panel")
                        ?.scrollIntoView({ behavior: "smooth" }),
                    300,
                  );
                }}
              >
                Investigate this observation →
              </button>
            </>
          ) : (
            <button onClick={onSubmit}>Submit a photo for review →</button>
          )}
          <p className="mission-footnote">
            Review time runs from submission to recorded decision, including
            operator delay.
          </p>
        </div>
        <div className="agent-work">
          <span className="eyebrow">REVIEW SEQUENCE</span>
          <p className="review-sequence-intro">A compact, traceable handoff from incoming observation to a human decision.</p>
          {(
            top?.agents || [
              {
                name: "Sentinel",
                method: "Trained YOLO11n",
                result: mission?.camera.running
                  ? "Monitoring selected camera"
                  : "Awaiting a camera frame or photo",
                status: "waiting",
              },
              {
                name: "Temporal analyst",
                method: "Distinct-frame comparison",
                result: "Collect successive frames to assess persistence",
                status: "waiting",
              },
              {
                name: "Evidence linker",
                method: "Time / distance matching",
                result: "Compare nearby reports and loaded thermal data",
                status: "waiting",
              },
              {
                name: "Investigation planner",
                method: "Auditable review rules",
                result: "Prioritize fresh evidence and missing checks",
                status: "waiting",
              },
            ]
          ).map((a, i) => (
            <div className="agent-task" key={`${i}-${a.name}`}>
              <span>{i + 1}</span>
              <div>
                <b>{["Photo screening", "Frame comparison", "Context matching", "Operator review"][i]}</b>
                <p>{a.result}</p>
                <small>
                  {a.method} · {a.status.replaceAll("_", " ")}
                </small>
              </div>
            </div>
          ))}
          <p className="mission-footnote">
            Vision uses the trained detector; evidence assessment and next
            actions use analysis rules.
          </p>
        </div>
      </div>
      <div className="station-network">
        <b>Observation network · select the next view</b>
        <p>
          Camera locations are visible on the map. A station location does not
          establish coverage of a suspected plume.
        </p>
        <div>
          {(mission?.cameras || []).map((c) => (
            <button
              key={c.id}
              onClick={async () => {
                try {
                  await api("/api/camera/select", { camera_id: c.id });
                  document
                    .querySelector(".camera-panel")
                    ?.scrollIntoView({ behavior: "smooth" });
                } catch (e) {
                  setError(e.message);
                }
              }}
            >
              {c.id === mission.selected_camera_id ? "● " : ""}
              {c.name} →
            </button>
          ))}
        </div>
      </div>
      <div className="community-purpose">
        <b>What reaches the operator?</b>
        <span>
          Original image → detection regions → corroboration & unknowns →
          recorded decision → exportable evidence packet.
        </span>
        <small>
          {mission?.community_outcome ||
            "Reports support human review; nearby matches do not confirm a shared event."}
        </small>
      </div>
    </section>
  );
}
