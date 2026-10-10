import React, { useCallback, useEffect, useState } from "react";

const stamp = (value) => value ? new Date(value).toLocaleString() : "timestamp unavailable";
const titleCase = (value) => String(value || "").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());

export default function ResponseResources({ latitude, longitude }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const point = `${Number(latitude).toFixed(5)}, ${Number(longitude).toFixed(5)}`;
  const refresh = useCallback(async (signal) => {
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({ latitude: String(latitude), longitude: String(longitude) });
      const response = await fetch(`/api/response-resources?${query}`, { signal });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || "Response information is temporarily unavailable.");
      }
      setData(await response.json());
    } catch (exception) {
      if (exception.name !== "AbortError") setError(exception.message);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [latitude, longitude]);
  useEffect(() => {
    const controller = new AbortController();
    refresh(controller.signal);
    return () => controller.abort();
  }, [refresh]);

  const evacuation = data?.sources?.evacuations;
  const stationSource = data?.sources?.fire_stations;
  const shelterSource = data?.sources?.shelters;
  const zones = evacuation?.zones || [];
  const orders = zones.filter((zone) => /order/i.test(zone.status));
  const warnings = zones.filter((zone) => /warning/i.test(zone.status));
  const shelters = shelterSource?.items || [];
  const stations = stationSource?.items || [];
  const loadedCount = (source) => source?.status === "loaded" ? source.items?.length ?? source.zones?.length ?? 0 : null;
  return (
    <section className="response-resources" aria-labelledby="response-resources-title">
      <div className="response-heading">
        <div>
          <span className="eyebrow">RESPONSE CONTEXT · CALIFORNIA</span>
          <h3 id="response-resources-title">Nearby alerts and resources</h3>
          <p>Live public records and mapped services around the affected-area point · {point}</p>
        </div>
        <button type="button" onClick={() => refresh()} disabled={loading}>{loading ? "Refreshing…" : "Refresh nearby data"}</button>
      </div>

      <div className="response-summary">
        <div className={`response-summary-card ${evacuation?.status === "loaded" && orders.length ? "is-order" : ""}`}>
          <span>CAL OES · evacuation orders</span>
          <strong>{evacuation?.status === "loaded" ? orders.length : "—"}</strong>
          <small>{evacuation?.status === "loaded" ? `${warnings.length} warning${warnings.length === 1 ? "" : "s"} within ${evacuation.coverage_radius_km} km` : "Feed unavailable"}</small>
        </div>
        <div className="response-summary-card">
          <span>Active fire stations</span>
          <strong>{loadedCount(stationSource) ?? "—"}</strong>
          <small>{stationSource?.status === "loaded" ? `Within ${stationSource.search_radius_km} km · CAL FIRE records` : "Source unavailable"}</small>
        </div>
        <div className="response-summary-card response-checked">
          <span>Community shelter listings</span>
          <strong>{loadedCount(shelterSource) ?? "—"}</strong>
          <small>{shelterSource?.status === "loaded" ? `Within ${shelterSource.search_radius_km} km · verify availability` : "Source unavailable"}</small>
        </div>
      </div>

      {error && <p className="response-inline-error" role="alert">{error}</p>}
      {loading && !data && <p className="response-loading" role="status">Loading official evacuation information and nearby mapped services…</p>}

      <div className="response-detail-grid">
        <section className="response-detail-card" aria-labelledby="evac-zone-title">
          <div className="response-detail-heading">
            <span className="response-icon response-icon-alert">!</span>
            <div><span className="eyebrow">OFFICIAL AGGREGATED FEED</span><h4 id="evac-zone-title">Evacuation status near this point</h4></div>
          </div>
          {evacuation?.status === "unavailable" ? (
            <p className="response-empty"><b>Could not load California evacuation data.</b><br />The app is not treating this as “no active orders.” Follow local emergency instructions.</p>
          ) : evacuation?.status === "loaded" && zones.length === 0 ? (
            <p className="response-empty"><b>No active zones were returned within the {evacuation.coverage_radius_km} km search radius.</b><br />Some jurisdictions do not share zones through this statewide feed; this does not prove no order applies.</p>
          ) : zones.length ? (
            <div className="response-zone-list">
              {zones.map((zone, index) => (
                <details className={`response-zone ${/order/i.test(zone.status) ? "zone-order" : /warning/i.test(zone.status) ? "zone-warning" : ""}`} key={`${zone.zone_id}-${index}`}>
                  <summary><span className="zone-status">{titleCase(zone.status)}</span><b>{zone.zone_name || zone.city || zone.county || "Active evacuation zone"}</b><small>{[zone.city, zone.county].filter(Boolean).join(" · ") || "Jurisdiction not provided"}</small></summary>
                  <div className="response-zone-body">
                    {zone.critical_info && <p><b>Critical information</b><br />{zone.critical_info}</p>}
                    {zone.public_info && <p><b>Public information</b><br />{zone.public_info}</p>}
                    <small>Zone {zone.zone_id || "ID unavailable"} · agency record updated {stamp(zone.updated_at)}</small>
                  </div>
                </details>
              ))}
            </div>
          ) : <p className="response-empty">Waiting for the evacuation feed…</p>}
          <small className="response-source-note">California Office of Emergency Services statewide county aggregation · advertised refresh cadence: 5 minutes · checked {stamp(evacuation?.checked_at)}.</small>
        </section>

        <section className="response-detail-card" aria-labelledby="fire-services-title">
          <div className="response-detail-heading">
            <span className="response-icon response-icon-station">+</span>
            <div><span className="eyebrow">CAL FIRE PUBLIC FACILITIES DATA</span><h4 id="fire-services-title">Nearby fire stations</h4></div>
          </div>
          {stationSource?.status === "unavailable" ? (
            <p className="response-empty"><b>CAL FIRE station data could not load.</b><br />No substitute results are displayed.</p>
          ) : stations.length ? (
            <ul className="response-facility-list">{stations.slice(0, 8).map((item, index) => <li key={`${item.name}-${index}`}><span className="facility-distance">{item.distance_km} km</span><div><b>{item.name}</b><small>{[item.county, item.type].filter(Boolean).join(" · ") || "Active facility"}</small><small>{item.address || "Address not listed"}</small>{item.phone && <small>Phone: {item.phone}</small>}</div></li>)}</ul>
          ) : stationSource?.status === "loaded" ? <p className="response-empty"><b>No active station facilities returned within {stationSource.search_radius_km} km.</b><br />This dataset covers participating state, local, and contract facilities; it is not a complete directory.</p> : <p className="response-empty">Waiting for CAL FIRE facility data…</p>}
          <small className="response-source-note">CAL FIRE Facilities for Wildland Fire Protection · active state, local, and contract station records · {stationSource?.search_radius_km ?? 75} km search · checked {stamp(stationSource?.checked_at)}.</small>
        </section>

        <section className="response-detail-card response-shelters" aria-labelledby="shelter-title">
          <div className="response-detail-heading">
            <span className="response-icon response-icon-shelter">⌂</span>
            <div><span className="eyebrow">NOT AN OFFICIAL DESTINATION LIST</span><h4 id="shelter-title">Mapped shelters nearby</h4></div>
          </div>
          {shelterSource?.status === "unavailable" ? <p className="response-empty">Community shelter listings could not be loaded. No substitute results are shown.</p> : shelters.length ? <ul className="response-facility-list">{shelters.slice(0, 6).map((item, index) => <li key={`${item.name}-${index}`}><span className="facility-distance">{item.distance_km} km</span><div><b>{item.name}</b><small>{item.address || item.operator || "Address not listed"}</small>{item.phone && <small>Phone: {item.phone}</small>}{item.opening_hours && <small>Hours: {item.opening_hours}</small>}</div></li>)}</ul> : shelterSource?.status === "loaded" ? <p className="response-empty">No community-mapped shelter entries returned within {shelterSource.search_radius_km} km. A mapped shelter is not necessarily open or designated for this incident.</p> : <p className="response-empty">Waiting for community shelter listings…</p>}
          <small className="response-source-note">OpenStreetMap community-mapped listings · {shelterSource?.search_radius_km ?? 20} km search · checked {stamp(shelterSource?.checked_at)}.</small>
        </section>
      </div>

      <aside className="response-safety-note">
        <b>Use current local instructions.</b> Orders and warnings shown here come from California’s public aggregation and may lag or omit a jurisdiction. Facility listings are community mapped and do not establish availability. This interface does not compute or certify a safe evacuation route, and no authority is contacted.
      </aside>
      <small className="response-pin-note">Affected-area point: {point} · separate from the observer/camera location. Sources last checked {data?.checked_at ? stamp(data.checked_at) : loading ? "in progress" : "not yet checked"}.</small>
    </section>
  );
}
