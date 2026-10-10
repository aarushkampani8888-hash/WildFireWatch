# WildfireWatch pitch video (about 2:45)

The ForgeHacks AI + Climate prompt asks for an AI-powered solution that helps people understand environmental changes, prepare for climate impacts, use resources wisely, or create resilient systems. This pitch focuses on a concrete resilience task: help local response teams turn scattered early wildfire signals into a source-traceable evidence handoff.

## Storyboard

| Time | Show | Narration |
|---|---|---|
| 0:00–0:20 | Open on the operator screen and the four-step Observe → Screen → Corroborate → Decide path. | “When a wildfire may be starting, a camera frame, a resident report, weather and satellite data can arrive separately. WildfireWatch brings those signals into one reviewable case so a local operator can decide what needs checking next.” |
| 0:20–0:45 | Show a current public camera frame, provider timestamp/source and the selected station’s live climate-context card. | “The station panel makes current wind, humidity, terrain and mapped surroundings visible. These conditions describe the camera area, not a confirmed fire location or the weather when an older image was captured.” |
| 0:45–1:10 | Upload a short video, then show the original clip, sampled frame findings and the model evaluation strip. | “Upload a short clip and WildfireWatch runs the same locally trained YOLO11n smoke detector on up to six evenly spaced frames. Smoke between samples can be missed. On held-out images, smoke recall was 76.8%, and 53.1% on a camera-disjoint Pyro-SDIS subset. Scores are uncalibrated; this is screening, not fire confirmation.” |
| 1:10–1:35 | Request the external second opinion; then load live regional signals. Show the map draw a NIFC perimeter beside the observer point and the NASA/NWS cards with provenance and timestamps. | “The trained smoke detector stays primary. An operator can request a separate vision opinion, then check satellite thermal pixels, official incident perimeters and active weather alerts. We show source, time and distance separately, never fabricate a combined probability.” |
| 1:35–2:00 | Show Community Evidence Relay and, if available, a second independent real report. | “The evidence linker surfaces reports that fall within a time-and-distance screen. A map connection is only a possible association for a person to review; it does not prove the reports share an event or locate an ignition. A missing satellite or perimeter match does not rule out a fire.” |
| 2:00–2:25 | Show LangGraph agent trace, next action, alternate camera controls, and the decision form. | “The temporal analyst checks distinct frames, the evidence linker compares nearby reports and loaded thermal data, and the planner names the next useful check. A human records the decision and its reasoning.” |
| 2:25–2:45 | Save the evidence packet and finish on the product name plus intended users. | “The intended impact is less manual cross-referencing and a clearer handoff for local response teams. We have not measured response-time or lives-saved benefits. WildfireWatch supports preparedness; it does not send emergency alerts or evacuation orders.” |

## Recording integrity

- Use real observation records with their correct sources, times and locations. Never attach a dataset photo to an invented California location or describe current weather as historical weather.
- If no nearby report exists, show the empty state and explain that the relay is ready to match future observations. Do not fabricate a real-world fire claim to make the feature appear active.
- If a controlled example is needed, use a separate, visibly labeled test environment and say which inputs and outcomes are simulated.
- Keep the uncalibrated score, weaker camera-disjoint recall, limited camera coverage and human-review step visible. Do not claim measured time saved, lives saved, source triangulation or safe evacuation routing.
- The external review sends the selected image, or up to two sampled video frames, to the configured OpenAI vision model only after the operator presses the button. If the backend has no key, omit that segment rather than staging a result.
- The regional signal check queries NIFC/WFIGS current perimeters and NOAA/NWS active weather alerts. NASA FIRMS thermal detections require a configured free MAP_KEY. Current perimeter and alert layers describe their own source timestamps; they do not prove that a report depicts that incident.
- Publish the video publicly and keep it between two and four minutes.
