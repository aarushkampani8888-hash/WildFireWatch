# Devpost submission copy

## Project title

WildfireWatch — Evidence Before Escalation

## Tagline

WildfireWatch brings smoke reports, camera footage, satellite clues, and local conditions into one map—so people can review evidence and decide what to check next.

## Track

AI + Climate

## Short description

WildfireWatch helps people review possible wildfire evidence in one map-based workspace. Its trained smoke detector screens submitted images and sampled video frames, while operators can compare reports with available thermal observations, public incident data, weather, and terrain context. A person records the decision; the prototype does not dispatch responders or issue evacuation guidance.

## What it does

Wildfire signals arrive in different places: a camera image, a community observation, a satellite thermal point, or a weather alert. WildfireWatch gives a reviewer one place to inspect those clues, see where each came from, and record what should happen next.

People can submit an observation with a photo or short video, observation time, optional viewing direction, and observer location. The locally run YOLO smoke detector screens an image or samples up to six frames from a video. Its results are advisory and uncalibrated: a detection does not confirm a wildfire, and a missed detection does not rule one out.

The operator map can display NASA FIRMS thermal observations alongside reports and public context. Thermal anomalies are leads, not verified incidents. Geographic and weather checks keep their source, timestamp, and coverage visible. When a source has not loaded, the interface distinguishes missing data from a negative finding.

After reviewing the evidence, a human can record a decision and notes. A confirmed-fire terrain scenario can animate illustrative reach envelopes using a selected point, current wind, local slope, and mapped land cover. The visualization is a demo sensitivity scenario, not a validated fire-growth forecast, evacuation boundary, or responder instruction.

## How we built it

The interface uses React, Vite, MapLibre, and OpenFreeMap terrain. A Python/FastAPI backend runs the fine-tuned YOLO11n smoke detector locally, coordinates report review with LangGraph, streams workflow updates over WebSockets, and stores decisions in SQLite. NASA FIRMS observations, NASA imagery, NIFC/WFIGS perimeters, NOAA/NWS alerts, Open-Meteo weather, and mapped terrain remain separate evidence sources with their own limitations.

The detector was fine-tuned on Pyro-SDIS v2 and D-Fire. On 5,240 held-out images, image-level smoke recall was 76.8% and precision was 95.1% at a 0.25 score threshold. Recall on a camera-disjoint Pyro-SDIS subset was 53.1%. Scores are not calibrated probabilities; D-Fire near-duplicate leakage has not been fully audited. These results are a development benchmark, not field validation.

## Why it matters

Wildfire response depends on timely, understandable evidence. WildfireWatch explores whether source-traceable review can reduce the manual effort of cross-checking early signals and make uncertainty clearer before a person escalates a case. We have not measured response-time or lives-saved benefits, and the prototype is not connected to emergency authorities.

## Built with

Python, FastAPI, React, Vite, MapLibre, OpenFreeMap, YOLO11n, PyTorch, LangGraph, SQLite, WebSockets, NASA FIRMS, NASA GIBS, NIFC/WFIGS, NOAA/NWS, Open-Meteo

## Current limitations

- Human review is required. Model scores are uncalibrated and do not equal fire probability.
- Thermal anomalies and proximity matches do not establish a wildfire or ignition location.
- The terrain spread animation is illustrative and is not suitable for evacuation or response decisions.
- Public data availability and coverage vary; missing data does not mean no fire.
- The prototype does not notify authorities, dispatch responders, or provide official emergency information.

## Team and AI-tool disclosure — fill in on Devpost

List every team member and their role. Disclose the AI coding tools used during development in the field provided by the hackathon. Confirm team eligibility and that the description accurately reflects work completed during ForgeHacks before submitting.
