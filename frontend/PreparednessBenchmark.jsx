import React, { useEffect, useMemo, useState } from "react";

const KEY = "wildfirewatch-preparedness-trials-v1";
const CASES = ["Possible smoke · single observation", "Camera sequence · persistence review", "Cross-source case · evidence packet"];
const format = (seconds) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
export default function PreparednessBenchmark({ className = "" }) {
  const [scenario, setScenario] = useState(CASES[0]);
  const [mode, setMode] = useState("with");
  const [running, setRunning] = useState(false);
  const [started, setStarted] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [trials, setTrials] = useState(() => { try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch { return []; } });
  useEffect(() => { localStorage.setItem(KEY, JSON.stringify(trials)); }, [trials]);
  useEffect(() => { if (!running) return; const id = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 250); return () => clearInterval(id); }, [running, started]);
  const paired = useMemo(() => {
    const groups = new Map();
    trials.filter((t) => t.scenario === scenario).forEach((t) => { const key = t.round; const row = groups.get(key) || {}; row[t.mode] = t.seconds; groups.set(key, row); });
    return [...groups.values()].filter((row) => Number.isFinite(row.with) && Number.isFinite(row.manual));
  }, [trials, scenario]);
  function start() { setStarted(Date.now()); setElapsed(0); setRunning(true); }
  function stop() {
    const seconds = Math.max(1, Math.floor((Date.now() - started) / 1000));
    const scenarioTrials = trials.filter((t) => t.scenario === scenario);
    const rounds = new Map();
    scenarioTrials.forEach((trial) => rounds.set(trial.round, [...(rounds.get(trial.round) || []), trial.mode]));
    const round = [...rounds.entries()].find(([, modes]) => !modes.includes(mode))?.[0]
      ?? (1 + Math.max(0, ...rounds.keys()));
    setTrials((items) => [...items, { scenario, mode, seconds, round, recordedAt: new Date().toISOString() }]);
    setElapsed(seconds); setRunning(false);
  }
  const avg = paired.length ? Math.round(paired.reduce((sum, p) => sum + (p.manual - p.with), 0) / paired.length) : null;
  return <section className={`preparedness-benchmark panel ${className}`} aria-labelledby="benchmark-title">
    <span className="eyebrow">MEASURE WORKFLOW · NO OUTCOME CLAIMS</span><h2 id="benchmark-title">Time an evidence-packet exercise</h2>
    <p>Run the same case with WildfireWatch and with your usual manual process. Time only from starting the review to completing a shareable evidence packet. Results stay in this browser.</p>
    <div className="benchmark-controls"><label>Repeatable case<select value={scenario} onChange={(e) => setScenario(e.target.value)} disabled={running}>{CASES.map((item) => <option key={item}>{item}</option>)}</select></label><label>Workflow<select value={mode} onChange={(e) => setMode(e.target.value)} disabled={running}><option value="with">With WildfireWatch</option><option value="manual">Manual baseline</option></select></label></div>
    <div className="benchmark-timer"><strong aria-live="polite">{format(elapsed)}</strong>{running ? <button className="primary" onClick={stop}>Stop and record</button> : <button className="primary" onClick={start}>Start timed trial</button>}</div>
    <p className="benchmark-result">{paired.length ? `${paired.length} paired round${paired.length === 1 ? "" : "s"} for this case · average time difference: ${avg > 0 ? `${format(avg)} faster with WildfireWatch` : avg < 0 ? `${format(Math.abs(avg))} faster manually` : "no average difference"}.` : "A comparison appears after one timed trial in each workflow for the same case."}</p>
    <small>Operator-timed demonstration only. Pair the same case and task; report sample count and raw times. This does not measure lives saved, detection accuracy, or emergency-response outcomes.</small>
    {trials.some((t) => t.scenario === scenario) && <details><summary>Recorded times for this case</summary><ul>{trials.filter((t) => t.scenario === scenario).map((t, i) => <li key={`${t.recordedAt}-${i}`}>Round {t.round} · {t.mode === "with" ? "WildfireWatch" : "Manual"} · {format(t.seconds)} · {new Date(t.recordedAt).toLocaleString()}</li>)}</ul><button onClick={() => setTrials((items) => items.filter((t) => t.scenario !== scenario))}>Clear this case’s trials</button></details>}
  </section>;
}
