# WildfireWatch demonstration: evidence before escalation

Audience: wildfire camera-monitoring operators and emergency operations staff. Residents are optional evidence contributors, not people sent to investigate hazards.

## Start

```sh
cd /Users/aarushkampani/Desktop/HTHS/wildfirewatch
ALLOWED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000 .venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/. The current server may already be running. Refresh the browser for the redesigned interface. Keep the terminal open; Control+C stops the server. No AI API credits are required.

## Three-minute video

For a live introduction, show **Live camera · trained model** before loading the staged example. Click **Analyze current frame**, then **Start live monitoring**. Show the HPWREN embedded timestamp, provider update time, inference score, and recent checks. The Los Pinos East camera is real incoming data; no smoke is guaranteed during the recording. Explain borderline sunset/cloud detections as candidates requiring human review. If a candidate is saved, open it in the inbox to show its camera source and the real LangGraph review trace. Stop monitoring when done. Use the clearly staged held-out smoke replay to reliably demonstrate the positive workflow without claiming that it is a current wildfire.

**0:00–0:20 — problem and users.** “Operators receive fragmented observations. WildfireWatch brings satellite context, community evidence, and trained smoke detection into one review workflow. This is a research prototype, not an official emergency channel.”

**0:20–0:55 — resident report.** Click **Load smoke evidence**. Explain that the image is held out from D-Fire and its assigned location/time are staged. Show observer coordinates, direction, time, and notes. Explain that a photographer's GPS does not locate the fire. Submit for local review.

**0:55–1:30 — actual AI.** The operator view opens the analyzed report. Show orange bounding boxes and the model score (~0.62). Explain YOLO11n was fine-tuned on both Pyro-SDIS and D-Fire and runs locally. Show the LangGraph stage trace. These are actual inference and backend events, not scripted predictions.

**1:30–2:00 — corroboration.** Inspect the staged hotspot match (within 25 km and 24 hours), clearly identifying it as invented replay data. Enable satellite imagery with date 2021-07-22: the NASA imagery itself is real historical data, unrelated to the D-Fire photo. Neither proximity nor imagery confirms this staged incident. If real FIRMS CSV/key is supplied, inspect actual source timestamps instead.

**2:00–2:25 — human decision.** Fetch current weather at the selected observer coordinates. Explain it is current weather, not 2021 incident weather. Add notes and choose **Need more evidence** or **Mark for escalation**. State that the decision persists locally, but no authority is notified.

**2:25–2:45 — lookalike.** Load and submit the cloud example. YOLO's maximum candidate score is about 0.066, below 0.25, so there is no displayed smoke box above threshold. “No smoke detected” is not proof of no fire.

**2:45–3:00 — limits and next steps.** Combined test recall is 76.8%, but unfamiliar Pyro-SDIS camera recall is 53.1%. Next steps: better small-smoke recall, secure deployment, authority partnerships, and validated camera localization. No lives-saved or operational response-speed claim has been measured.

## Demonstration integrity

- Bundled images are held-out examples, not a complete performance benchmark. Full metrics are in `models/detector-card.json`.
- Staged coordinates/time and thermal point are explicitly labeled, and never mixed into normal-report matching.
- NASA imagery is separate from NASA thermal-detection records and is not processed by the ground-camera YOLO model.
- Never describe a recorded escalation as a dispatch to authorities or a candidate route as an approved evacuation instruction.
- Local reports/photos persist in `data/reports.sqlite`; do not publish this database.
- Real satellite refresh requires a free NASA FIRMS key. Without it, use CSV import or explicitly staged replay—do not imply live statewide monitoring.
