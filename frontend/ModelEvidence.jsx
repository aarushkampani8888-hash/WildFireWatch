import React from "react";
const MODELS = [
  {
    name: "Our trained YOLO11n",
    state: "Active detector",
    recall: "74.1%",
    falseAlarms: "4.3%",
    cameraRecall: "43.8%",
    latency: "0.03 s",
    active: true,
  },
  {
    name: "Pyronear YOLOv8s",
    state: "Evaluated · not enabled",
    recall: "52.8%",
    falseAlarms: "14.3%",
    cameraRecall: "57.5%",
    latency: "0.58 s",
  },
  {
    name: "Quick Quokka YOLO11s",
    state: "Camera specialist candidate · not enabled",
    recall: "43.3%",
    falseAlarms: "5.2%",
    cameraRecall: "96.2%",
    latency: "0.46 s",
  },
];
export default function ModelEvidence({ available, className = "" }) {
  return (
    <details className={`model-evidence panel ${className}`}>
      <summary>
        <span>Model evidence & comparison</span>
        <small>
          {available
            ? "Our detector is active"
            : "Backend required to run our detector"}{" "}
          · 2 evaluated candidates
        </small>
      </summary>
      <div className="model-evidence-content">
        <div className="section-intro">
          <span className="eyebrow">
            Measured performance, not a confidence promise
          </span>
          <h2>Different models suit different images.</h2>
          <p>
            A reproducible 512-image screening: 282 smoke and 230 clear images.
            All images were held out from our model's training.
          </p>
        </div>
        <div className="model-cards">
          {MODELS.map((m) => (
            <article
              key={m.name}
              className={m.active ? "model-card model-active" : "model-card"}
            >
              <span
                className={m.active ? "model-status active" : "model-status"}
              >
                {m.active && !available
                  ? "Configured detector · offline"
                  : m.state}
              </span>
              <h3>{m.name}</h3>
              <dl>
                <div>
                  <dt>Smoke images detected · overall</dt>
                  <dd>{m.recall}</dd>
                </div>
                <div>
                  <dt>False alarms · clear images</dt>
                  <dd>{m.falseAlarms}</dd>
                </div>
                <div>
                  <dt>Distant Pyro camera smoke detected</dt>
                  <dd>{m.cameraRecall}</dd>
                </div>
                <div>
                  <dt>Median local CPU inference</dt>
                  <dd>{m.latency}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
        <div className="evaluation-note">
          <b>What this means for the operator</b>
          <p>
            Keep our model for general photo reports. Quick Quokka is a
            promising camera-specific second opinion, but has not been enabled
            or validated on live HPWREN footage. A model score never replaces a
            human review.
          </p>
        </div>
        <p className="evaluation-caveat">
          Fixed thresholds: our model 0.25; providers 0.20. This is a sample,
          not the full 5,240-image test set. External training overlap is
          unknown; the Pyro subset has only 12 clear images. Timing is on a
          local Mac, not this server. Scores are uncalibrated.
        </p>
        <div className="evaluation-sources">
          <a
            href="https://huggingface.co/pyronear/yolov8s"
            target="_blank"
            rel="noreferrer"
          >
            YOLOv8s model card ↗
          </a>
          <a
            href="https://huggingface.co/pyronear/yolo11s_quick-quokka_v8.0.0"
            target="_blank"
            rel="noreferrer"
          >
            Quick Quokka model card ↗
          </a>
        </div>
      </div>
    </details>
  );
}
