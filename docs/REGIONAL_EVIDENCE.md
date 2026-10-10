# Live regional evidence

In an evidence review, select **Check regional signals**. The backend queries three independent feeds concurrently and reports each source separately:

- NIFC/WFIGS current interagency perimeters within 75 km of the observer point. The map overlays returned geometries and the card shows the reported perimeter update time and approximate distance. The service does not contain a published perimeter for every incident.
- NOAA/NWS active alerts at the observer point, filtered to fire, smoke, wind, heat and Red Flag context. These are current weather alerts, not alerts tied to the submitted incident.
- NASA FIRMS VIIRS NOAA-20 near-real-time detections within 25 km and 24 hours of the report time. This source requires `FIRMS_MAP_KEY`; an old report is marked time-mismatched instead of being paired with today's satellite observations.

NIFC perimeters and NWS alerts are queried on demand without a provider key. Configure `FIRMS_MAP_KEY` in the backend environment for live FIRMS access. The check is disabled for reference media because the supplied coordinates are not verified capture coordinates. If one feed fails, the other source cards still render with an unavailable state.

The screen is an evidence comparison, not an automated fire classifier. A perimeter may be absent or stale; a thermal pixel may be a non-fire heat source; an alert describes broader weather conditions. No weighted score or fire probability is calculated, and the tool does not send emergency notifications.
