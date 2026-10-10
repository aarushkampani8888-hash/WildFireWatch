# WildfireWatch investigation walkthrough

1. Open the connected app and sign in to the private operator session.
2. Choose a camera and start live monitoring. Allow at least two minutes for distinct provider images. Expand **Compare recent frames** to inspect the original timestamped snapshots, scores, and temporal comparison. Unchanged or stale images do not count as new evidence.
3. Open a camera candidate in the inbox (or use **Analyze sample smoke** for a clearly staged still-image demo). Select **Open investigation** in Evidence review.
4. Review Supporting evidence, Evidence that weakens suspicion, and Unresolved questions. Persistence alone does not distinguish a fixed light/cloud from smoke. Box area and center changes are image-plane measurements, not physical spread or object tracking.
5. Use **Inspect [nearby camera]** for a second view. These cameras are ranked by observer distance; overlapping coverage is not established. The original feed stops, and a fresh frame is requested from the new feed. Inspect the image in Live camera monitoring and explicitly start continued monitoring if wanted.
6. Load geographic/weather context. Attach context using **Gather geographic context for evidence packet** before downloading. Current weather is not historical incident weather. Elevation and weather are working; vegetation/development can remain unavailable if the map provider fails.
7. Expand **Satellite data & provenance** to load live NASA FIRMS if configured or import FIRMS CSV. The investigation refreshes its time/distance matching against loaded observations. Missing thermal evidence does not rule out a fire; nearby detections do not establish the same fire.
8. Record an operator decision and notes. Download the JSON evidence packet: original image, detector finding, timestamps and source metadata, temporal measurements, loaded thermal matches, attached context, unknowns, workflow events, and decision. No notification or evacuation order is sent.

For a contrast demo, analyze both bundled smoke and cloud-lookalike images. Real local inference runs on each; their assigned location/time and demo thermal observation are staged. These are still-image examples, not validated temporal videos. Do not claim automated light/cloud rejection, fire triangulation, calibrated fire probability, or statewide surveillance.

Live sequence images are bounded to six in memory and clear when switching cameras or restarting the backend. Temporal metadata associated with a camera candidate persists in its report for a ten-minute comparison window. Recent-frame comparisons are deterministic screening using the trained detector's outputs, not a second VLM.
