const assert = require("node:assert/strict");

(async () => {
  const { buildFireScenario } = await import("../frontend/fireScenario.js");
  const center = { latitude: 37.5, longitude: -119.5 };
  const context = {
    weather: { wind_speed_10m: 32, wind_direction_10m: 0 },
    terrain: { slope_degrees: 20 },
    landscape: { cover: ["wood"] },
    assessed_at: "2026-10-10T12:00:00Z",
  };

  const scenario = buildFireScenario(center, context, 0.6);
  assert.equal(scenario.features.length, 3);
  assert.deepEqual(scenario.features.map(({ properties }) => properties.minutes), [120, 60, 30]);
  assert.ok(scenario.metrics.paceKmPerHour > 0.6);
  assert.ok(scenario.features[0].properties.distance_km > scenario.features[1].properties.distance_km);
  assert.ok(scenario.features[0].properties.area_km2 > scenario.features[1].properties.area_km2);
  assert.equal(scenario.features[0].geometry.coordinates[0].length, 74);
  const meanLatitude = scenario.features[1].geometry.coordinates[0]
    .slice(0, -1)
    .reduce((total, point) => total + point[1], 0) / 73;
  assert.ok(meanLatitude < center.latitude, "wind-from-north envelope should extend south");
  assert.equal(buildFireScenario(center, { ...context, weather: null }), null);
  assert.equal(buildFireScenario(center, { ...context, terrain: { slope_degrees: null } }), null);

  const noMappedCover = buildFireScenario(center, {
    ...context,
    landscape: { cover: [] },
  });
  assert.ok(scenario.metrics.paceKmPerHour > noMappedCover.metrics.paceKmPerHour);
  console.log("fire scenario envelope checks passed");
})();
