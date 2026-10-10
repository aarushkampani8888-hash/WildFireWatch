export const nodes = {
  community: [3, 6],
  junction: [5, 6],
  ridge: [6, 4],
  east: [9, 4],
  south: [5, 9],
  shelter: [10, 9],
  west: [1, 8],
};
export const edges = [
  ["community", "junction", 3],
  ["junction", "ridge", 3],
  ["ridge", "east", 4],
  ["east", "shelter", 5],
  ["junction", "south", 4],
  ["south", "shelter", 6],
  ["community", "west", 3],
  ["west", "south", 6],
];
export function project(w, h, d, m) {
  const a = 0.25 + (m / 60) * (0.5 + w * 0.045) * (1 - h * 0.006),
    b = 0.2 + (m / 60) * 0.35,
    t = ((d + 180) * Math.PI) / 180,
    dx = Math.sin(t),
    dy = -Math.cos(t),
    center = [6 + dx * a * 0.55, 5 + dy * a * 0.55];
  return {
    minutes: m,
    a,
    b,
    direction: d,
    center,
    points: Array.from({ length: 65 }, (_, i) => {
      let t = (i * Math.PI * 2) / 64;
      return [
        center[0] + dx * a * Math.cos(t) - dy * b * Math.sin(t),
        center[1] + dy * a * Math.cos(t) + dx * b * Math.sin(t),
      ];
    }),
  };
}
export function inside(point, p) {
  let t = ((p.direction + 180) * Math.PI) / 180,
    dx = Math.sin(t),
    dy = -Math.cos(t),
    x = point[0] - p.center[0],
    y = point[1] - p.center[1];
  return ((x * dx + y * dy) / p.a) ** 2 + ((-x * dy + y * dx) / p.b) ** 2 <= 1;
}
export function simulate(data) {
  let projections = [30, 60, 120].map((m) =>
      project(data.wind, data.humidity, data.direction, m),
    ),
    p = projections.find((p) => p.minutes === data.horizon),
    graph = Object.fromEntries(Object.keys(nodes).map((n) => [n, []])),
    excluded = [];
  for (let [a, b, c] of edges) {
    let hit = Array.from({ length: 101 }, (_, i) => [
      nodes[a][0] + ((nodes[b][0] - nodes[a][0]) * i) / 100,
      nodes[a][1] + ((nodes[b][1] - nodes[a][1]) * i) / 100,
    ]).some((pt) => inside(pt, p));
    if (hit || data.closures.includes(a + "-" + b)) {
      excluded.push({
        edge: a + "-" + b,
        reason: hit ? "projected hazard" : "operator closure",
      });
      continue;
    }
    let weight = c * ([a, b].includes("south") ? data.congestion : 1);
    graph[a].push([b, weight]);
    graph[b].push([a, weight]);
  }
  let q = [[0, "community", ["community"]]],
    seen = new Set(),
    route = { path: [], minutes: null, excluded, status: "no_route" };
  while (q.length) {
    q.sort((a, b) => a[0] - b[0]);
    let [cost, n, path] = q.shift();
    if (seen.has(n)) continue;
    seen.add(n);
    if (n === "shelter") {
      route = {
        path,
        minutes: Math.round(cost * 10) / 10,
        excluded,
        status: "candidate",
      };
      break;
    }
    for (let [next, w] of graph[n])
      if (!seen.has(next)) q.push([cost + w, next, [...path, next]]);
  }
  return {
    id: crypto.randomUUID().slice(0, 8),
    time: new Date().toISOString(),
    sentinel: {
      smoke_detected: true,
      confidence: 0.91,
      reason: "Scripted smoke event in the synthetic Ridge camera scene.",
      source: "simulation",
    },
    weather: {
      wind: data.wind,
      humidity: data.humidity,
      direction: data.direction,
      source: data.weather_source,
    },
    projections,
    route,
    nodes,
    edges,
    horizon: data.horizon,
    events: [
      {
        agent: "Sentinel",
        message: "Scripted smoke event in the synthetic Ridge camera scene.",
      },
      {
        agent: "Propagator",
        message: "Generated illustrative 30 / 60 / 120 minute envelopes.",
      },
      {
        agent: "Dispatcher",
        message: route.path.length
          ? "Candidate corridor: " + route.path.join(" → ")
          : "No corridor generated. Human review required.",
      },
    ],
  };
}
