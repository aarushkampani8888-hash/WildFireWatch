# Video upload pack — separate from the product UI

These are unmodified held-out D-Fire images from the existing project dataset. Capture location and time are unknown. Dataset labels can contain errors; they are not operator confirmation. The model has already been evaluated on these examples, so this is a curated demonstration, not a fresh blind accuracy test.

## Input for every upload
1. Click **New observation** / **Report observed smoke** and upload one JPG from this folder.
2. Check **Reference image · supplied location/time are test values**.
3. For required test coordinates enter **32.73467, -116.57775**. These are assigned test values, not where the dataset photo was captured. Leave viewing direction blank because it is unknown. Use the current UTC time offered by the form solely as the test submission time.
4. Enter a note such as: “Reference dataset photo; original location/time unknown. Inspect possible smoke and confounders.”
5. Submit, inspect boxes and the investigation, then record a human decision and notes. Reference submissions are excluded from the incident map and satellite matching.

## Suggested video sequence (3–4 minutes)
- 01-clear-road.jpg: establish the ordinary upload workflow and below-threshold case.
- 02-dense-wildfire-smoke.jpg: inspect candidate outlines, detector score and human-review action.
- 03-distant-smoke.jpg: show a less obvious plume.
- 06-subtle-smoke.jpg: show a real limitation if the detector misses this labeled smoke example; use “Need more evidence,” rather than calling the scene safe.
- 08-storm-lookalike.jpg: show why a candidate needs human review. If flagged, inspect the storm/rain confounder and record your assessment; no automated rejection is claimed.
- Optionally show 04, 05, 07 and 09 for urban fire, nighttime fire, haze and lights.

Use cases.csv for scores observed with the actual local production inference path. Scores may differ slightly on the hosted runtime. These are uncalibrated model scores, not the probability that a fire exists. Do not turn a dataset “no smoke” label into a claim of safety. Do not present still images as a temporal sequence or claim their test locations corroborate satellite evidence.

For the live portion, return to Live camera monitoring, start a camera, wait for two or more distinct minute snapshots, and open Compare recent frames. This demonstrates real temporal collection separately from these unrelated reference photos. No thermal CSV is fabricated for this pack. Real satellite demonstration requires a sourced FIRMS CSV with genuine acquisition dates and coordinates.

Source: https://github.com/gaia-solutions-on-demand/DFireDataset (collection distributed as CC0-1.0; preserve original image credits/watermarks). manifest.json records exact hashes, dataset labels and detector findings. No image pixels were modified.

## Observed results on this machine
- 01-clear-road.jpg: 0.0% score, below threshold; dataset smoke label False.
- 02-dense-wildfire-smoke.jpg: 83.9% score, candidate; dataset smoke label True.
- 03-distant-smoke.jpg: 76.3% score, candidate; dataset smoke label True.
- 04-urban-house-fire.jpg: 83.9% score, candidate; dataset smoke label True.
- 05-night-fire.jpg: 76.8% score, candidate; dataset smoke label True.
- 06-subtle-smoke.jpg: 0.0% score, below threshold; dataset smoke label True.
- 07-hazy-camera.jpg: 0.0% score, below threshold; dataset smoke label False.
- 08-storm-lookalike.jpg: 35.6% score, candidate; dataset smoke label False.
- 09-night-lights.jpg: 25.2% score, candidate; dataset smoke label False.
