const rad = (degrees) => (degrees * Math.PI) / 180;

function destination(longitude, latitude, bearing, distanceKm) {
  const angular = distanceKm / 6371;
  const lat1 = rad(latitude);
  const lon1 = rad(longitude);
  const heading = rad(bearing);
  const lat2 = Math.asin(
    Math.sin(lat1) * Math.cos(angular) +
      Math.cos(lat1) * Math.sin(angular) * Math.cos(heading),
  );
  const lon2 =
    lon1 +
    Math.atan2(
      Math.sin(heading) * Math.sin(angular) * Math.cos(lat1),
      Math.cos(angular) - Math.sin(lat1) * Math.sin(lat2),
    );
  return [(lon2 * 180) / Math.PI, (lat2 * 180) / Math.PI];
}

function ellipse(center, downwindBearing, alongKm, crossKm) {
  const downwind = rad(downwindBearing);
  const points = [];
  for (let index = 0; index <= 72; index += 1) {
    const angle = (index / 72) * Math.PI * 2;
    const along = alongKm * Math.cos(angle);
    const cross = crossKm * Math.sin(angle);
    const east = along * Math.sin(downwind) + cross * Math.cos(downwind);
    const north = along * Math.cos(downwind) - cross * Math.sin(downwind);
    const distance = Math.hypot(east, north);
    points.push(
      destination(center.longitude, center.latitude, Math.atan2(east, north) * 180 / Math.PI, distance),
    );
  }
  return [...points, points[0]];
}

/**
 * Demo sensitivity envelope only. Its pace is an explicit user-selected
 * assumption, not a field-calibrated fire behavior model or forecast.
 */
export function buildFireScenario(center, assessment, paceKmPerHour = 0.6) {
  const weather = assessment?.weather;
  const slope = assessment?.terrain?.slope_degrees;
  if (
    !center ||
    !weather ||
    !Number.isFinite(weather.wind_speed_10m) ||
    !Number.isFinite(weather.wind_direction_10m) ||
    !Number.isFinite(slope)
  ) return null;

  const cover = assessment.landscape?.cover || [];
  const vegetationFactor = cover.some((item) => ["wood", "forest", "scrub", "heath"].includes(item))
    ? 1.15
    : cover.some((item) => ["grass", "grassland", "meadow", "orchard", "farmland"].includes(item))
      ? 1.05
      : 1;
  const windFactor = 1 + Math.min(weather.wind_speed_10m, 80) / 160;
  const slopeFactor = 1 + Math.min(slope, 45) / 180;
  const scenarioPace = paceKmPerHour * windFactor * slopeFactor * vegetationFactor;
  const downwindBearing = (weather.wind_direction_10m + 180) % 360;
  const features = [120, 60, 30].map((minutes) => {
    const distanceKm = scenarioPace * minutes / 60;
    const centerOffset = distanceKm * 0.42;
    const alongKm = Math.max(distanceKm * 0.58, 0.08);
    const crossKm = Math.max(distanceKm * 0.42, 0.06);
    const [longitude, latitude] = destination(
      center.longitude, center.latitude, downwindBearing, centerOffset,
    );
    const shiftedCenter = { longitude, latitude };
    return {
      type: "Feature",
      properties: {
        minutes,
        distance_km: Number(distanceKm.toFixed(2)),
        area_km2: Number((Math.PI * alongKm * crossKm).toFixed(2)),
      },
      geometry: {
        type: "Polygon",
        coordinates: [[
          ...ellipse(
            shiftedCenter,
            downwindBearing,
            alongKm,
            crossKm,
          ),
        ]],
      },
    };
  });
  return {
    type: "FeatureCollection",
    features,
    metrics: {
      paceKmPerHour: Number(scenarioPace.toFixed(2)),
      windKmh: weather.wind_speed_10m,
      windFromDegrees: weather.wind_direction_10m,
      slopeDegrees: slope,
      vegetation: cover.length ? cover.join(", ") : "No mapped vegetation tags",
      vegetationFactor,
      assessedAt: assessment.assessed_at,
    },
  };
}
