import React, { useEffect, useState } from "react";

const CASES = [
  { date: "2021-08-01", acres: 248570, containment: 33, url: "https://osfm.fire.ca.gov/incidents/2021/7/13/dixie-fire/updates/9198bd09-609e-44d6-b371-300688af02da/", note: "CAL FIRE reported perimeter area and containment; crews described perimeter-line work and warmer, drier conditions." },
  { date: "2021-08-05", acres: 322502, containment: 35, url: "https://www.fire.ca.gov/incidents/2021/7/13/dixie-fire/updates/1f8d8b8e-d745-4fb8-8ea5-8e3ac0f98424/", note: "CAL FIRE reported 50,000 acres of overnight growth driven by low humidity and strong winds." },
  { date: "2021-08-07", acres: 446723, containment: 21, url: "https://www.fire.ca.gov/incidents/2021/7/13/dixie-fire/updates/a758abdc-241a-4854-b550-43363617850d/", note: "CAL FIRE described minimal overnight activity under an inversion, but historically low fuel moisture and sparse fuels in the Moonlight Fire scar." },
  { date: "2021-08-18", acres: 635728, containment: 33, url: "https://www.fire.ca.gov/incidents/2021/7/13/dixie-fire/updates/515763bf-6c31-45ee-9a40-d26bbbcdb5cb", note: "CAL FIRE described shifting winds, spotting, red-flag weather, and continued fire-front movement." },
];

export default function HistoricalReplay({ onReplay, className = "" }) {
  const [index, setIndex] = useState(0);
  const [weather, setWeather] = useState(null);
  const [weatherStatus, setWeatherStatus] = useState("Loading historical weather…");
  const [mapStatus, setMapStatus] = useState("");
  const step = CASES[index];
  useEffect(() => {
    const controller = new AbortController();
    setWeather(null);
    setWeatherStatus("Loading historical weather…");
    const url = new URL("https://archive-api.open-meteo.com/v1/archive");
    url.search = new URLSearchParams({ latitude: "39.98", longitude: "-121.1", start_date: step.date, end_date: step.date, daily: "temperature_2m_max,precipitation_sum,wind_speed_10m_max", timezone: "America/Los_Angeles" });
    fetch(url, { signal: controller.signal }).then((r) => { if (!r.ok) throw Error("Unavailable"); return r.json(); }).then((data) => {
      const d = data.daily;
      if (!d?.time?.length) throw Error("No historical record returned");
      setWeather({ high: d.temperature_2m_max?.[0], rain: d.precipitation_sum?.[0], wind: d.wind_speed_10m_max?.[0] });
      setWeatherStatus(`Open-Meteo archive · daily values for ${step.date}`);
    }).catch((error) => { if (error.name !== "AbortError") setWeatherStatus("Historical weather unavailable for this date · no values inferred"); });
    return () => controller.abort();
  }, [step.date]);
  function select(next) {
    setIndex(next);
    onReplay?.({ date: CASES[next].date, center: [-121.1, 39.98] });
    setMapStatus(`Map updated to ${CASES[next].date}: centered near Feather River Canyon with NASA Terra imagery enabled.`);
  }
  function showOnMap() {
    onReplay?.({ date: step.date, center: [-121.1, 39.98] });
    setMapStatus(`Map centered near Feather River Canyon for ${step.date}; NASA Terra imagery is set to this date.`);
  }
  return <section className={`historical-replay panel ${className}`} aria-labelledby="historical-replay-title">
    <div className="historical-replay-head"><div><span className="eyebrow">DOCUMENTED PAST FIRE · NOT LIVE CONDITIONS</span><h2 id="historical-replay-title">Dixie Fire historical replay</h2><p>Scrub dated NASA true-color imagery beside CAL FIRE’s contemporaneous perimeter acreage, conditions, and archived weather.</p></div><div className="replay-stepper"><button aria-label="Previous replay date" onClick={() => select(Math.max(0, index - 1))} disabled={index === 0}>←</button><input aria-label="Historical replay step" type="range" min="0" max={CASES.length - 1} step="1" value={index} onChange={(e) => select(Number(e.target.value))}/><button aria-label="Next replay date" onClick={() => select(Math.min(CASES.length - 1, index + 1))} disabled={index === CASES.length - 1}>→</button></div></div>
    <div className="replay-dates">{CASES.map((item, i) => <button key={item.date} className={i === index ? "active" : ""} onClick={() => select(i)}>{new Date(`${item.date}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</button>)}</div>
    <div className="replay-facts"><div><small>CAL FIRE report · {step.date}</small><b>{step.acres.toLocaleString()} acres</b><span>Reported fire area · {step.containment}% contained</span></div><div><small>Historical weather · near Feather River Canyon</small><b>{weather ? `${weather.high ?? "—"} °C max · ${weather.wind ?? "—"} km/h max wind` : weatherStatus}</b><span>{weather ? `${weather.rain ?? "—"} mm daily precipitation · ${weatherStatus}` : "No weather value is shown until the archive responds."}</span></div></div>
    <p className="replay-note">{step.note} The acreage values are official reported snapshots, not a time-series perimeter polygon or a forward forecast. NASA imagery availability varies by date; cloud and smoke can obscure the ground. Selecting a date updates the map to that date’s imagery and recenters it near Feather River Canyon.</p>
    <div className="replay-sources"><a href={step.url} target="_blank" rel="noreferrer">Open this dated CAL FIRE status update ↗</a><a href="https://www.arcgis.com/home/item.html?id=2140078c59714858b67feb33df4bc69e" target="_blank" rel="noreferrer">NIFC historical perimeter archive ↗</a><a href="https://gibs.earthdata.nasa.gov/" target="_blank" rel="noreferrer">NASA GIBS imagery ↗</a></div>
    <button className="replay-map-button" onClick={showOnMap}>Center map on {step.date}</button>
    {mapStatus && <small className="replay-map-status" role="status">{mapStatus}</small>}
  </section>;
}
