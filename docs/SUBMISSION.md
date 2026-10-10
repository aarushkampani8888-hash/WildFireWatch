# Submission draft

**Title:** WildfireWatch — Evidence Before Escalation

**Track:** AI + Climate

**Tagline:** Connect camera and community observations so operators can decide what needs checking next.

## Problem and intended users

Wildfire-monitoring staff face scattered camera images, weather, satellite observations, and resident reports. Reviewing the evidence and its uncertainty in one place could reduce manual cross-referencing. Residents already observing smoke from a safe place can contribute photos; the platform does not ask people to approach hazards.

## Fit to the AI + Climate prompt

The project helps local response teams understand changing environmental conditions around monitored communities and prepare a more resilient evidence handoff when a wildfire signal appears. It connects camera observations and community reports with current weather, mapped landscape context, and available thermal observations. The climate panel describes current conditions near the selected camera station; it is not a fire-danger forecast, does not locate the fire, and does not attribute an individual fire to climate change.

## What we built

A community reporting view accepts a photo or a short MP4, WebM, or MOV clip, along with observer coordinates, viewing direction, observation time, and notes. For video, the backend preserves the original clip and runs the trained YOLO smoke detector on up to six evenly spaced frames, showing each sampled result and its offset in the clip. Smoke that appears between samples can be missed; the model screens for smoke and does not confirm fire or flames. The LangGraph workflow runs intake, detection, time/distance matching, and a human-review stage; events stream over WebSockets. The evidence packet surfaces nearby submissions, loaded thermal observations, camera-frame history, image detections, and unresolved questions. A time/distance match is a lead for an operator to inspect, not confirmation that reports describe one fire. Operator decisions and notes persist in SQLite.

The demonstration can use a clearly labeled held-out photo with staged coordinates/time, or an actual community report. NASA GIBS imagery is historical context and is not imagery of a submitted photo. Live NASA FIRMS refresh was verified on October 10, 2026 and loaded 23 California thermal observations in that session; availability and counts vary. Thermal points are leads, not verified fires. No authority is notified.

For a report, the operator can request a public-data check: NIFC/WFIGS current incident perimeters, NOAA/NWS active fire-weather alerts, and NASA FIRMS/VIIRS detections when configured. Public layers are shown with provenance, freshness, and distance. An external vision review is separately operator-triggered. Sources remain independent; there is no calibrated fused probability, and a missing match is not evidence that no fire exists.

## Technical implementation
The local backend can sample one HPWREN Los Pinos East research camera every minute. Each new frame goes through the trained YOLO detector; threshold-crossing candidates enter the LangGraph report workflow and SQLite inbox. This is one research feed, with no statewide coverage or confirmed-fire guarantee. The map also offers a confirmed-fire terrain scenario: its animated envelopes are illustrative sensitivity visuals, not a validated fire-growth forecast or evacuation guidance.

React/Vite, MapLibre/OpenFreeMap terrain, Python/FastAPI, LangGraph, WebSockets, SQLite, YOLO11n/PyTorch, NASA GIBS imagery, NASA FIRMS thermal data, NIFC/WFIGS perimeters, NOAA/NWS active alerts, and Open-Meteo weather. The smoke detector was fine-tuned for 15 epochs using 25,065 images from Pyro-SDIS v2 and D-Fire, with separate validation and test splits. Combined image-level test precision is 95.1%, recall 76.8%, and false-positive rate 4.9% at score 0.25. Recall on unfamiliar Pyro-SDIS cameras is 53.1%; D-Fire near-duplicate leakage is not fully audited.

## Impact and limits

The intended benefit is less manual cross-referencing and clearer evidence handoff. Response-time and lives-saved benefits have not been measured. Observer locations do not identify ignition; proximity does not establish the same fire. Satellite imagery is not analyzed by our ground-camera model. The installation lacks production community moderation, secure authority integration, and statewide camera coverage. Spread/routing endpoints are not used to issue evacuation guidance.

## Demonstration and checklist

Use `docs/VIDEO_DEMO_SCRIPT.md` for the conversational 2–4 minute demo script and `submission-ready/README_FIRST.md` for the complete upload kit. Deployment is optional under the published submission requirements.

- Publish source and clear README on GitHub (or arrange organizer access as allowed by the rules).
- Provide trusted trained weights/setup instructions so model inference is reproducible; weights are omitted from the Git source by default.
- Record a public 2–4 minute video with actual local inference.
- Include screenshots/architecture and accurate source/provenance labels.
- List every team member, disclose AI coding assistance, and confirm eligibility/track prompt.
- Submit before the official deadline; recheck Devpost for current requirements.
