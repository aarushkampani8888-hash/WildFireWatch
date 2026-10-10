# Confirmed-fire terrain scenario

This map layer is a visual sensitivity demo, not a fire-growth forecast. It is only shown after an operator records a human-confirmed fire and selects an affected-area point. The selected point is treated as an origin proxy; it is not inferred from a smoke image.

The operator chooses a base pace between 0.2 and 1.5 km/h. The display applies transparent demo multipliers:

- Wind: 1 + min(10 m wind speed, 80 km/h) / 160
- Slope: 1 + min(point slope, 45 degrees) / 180
- Mapped cover: 1.15 for mapped woody cover, 1.05 for mapped grass cover, and 1.0 otherwise

The resulting scenario pace is multiplied by 0.5, 1, and 2 hours to make the 30-, 60-, and 120-minute reach bands. The ellipses point downwind using the current Open-Meteo wind direction and use a fixed crosswind proportion. The displayed area is the geometric ellipse area, not expected burned area or exposed population. A pulsing orange/red outline distinguishes the layer visually; it is not a thermal observation.

Weather is a gridded current estimate. Slope is estimated locally from a 90 m DEM over about 600 m. OpenStreetMap cover tags are incomplete. This view does not contain a measured fire perimeter, spatial fuel model, fuel moisture, spotting, suppression, fire acceleration, crown-fire behavior, or terrain-adjusted wind fields. The static coefficients are not calibrated to observed fires and are not the Rothermel, Behave, FARSITE, or FlamMap models. Do not use its reach or footprint for evacuation, response assignment, arrival-time estimates, or public warnings.

For longer-term context, consult CAL FIRE Fire Hazard Severity Zones and the weekly U.S. Drought Monitor separately. Neither is a real-time fire-spread prediction or point fuel-moisture measurement.
