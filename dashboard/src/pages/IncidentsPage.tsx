import { useCallback, useEffect, useState } from "react";
import { getIncidents } from "../api/client";
import type { Incident } from "../api/client";
import { useTimezone } from "../theme/TimezoneContext";

export default function IncidentsPage() {
  const { formatDateTime, formatTime } = useTimezone();
  const [scenarioRunId, setScenarioRunId] = useState("run-ros2-live");
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await getIncidents(scenarioRunId || undefined);
      setIncidents(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load incidents");
    }
  }, [scenarioRunId]);

  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [load]);

  return (
    <div>
      <div className="controls">
        <label>
          Scenario run ID{" "}
          <input
            value={scenarioRunId}
            onChange={(e) => setScenarioRunId(e.target.value)}
          />
        </label>
        <button type="button" className="btn-primary" onClick={load}>Refresh</button>
      </div>
      {error && <p className="error">{error}</p>}
      {incidents.length === 0 && !error && (
        <p className="empty-hint">No incidents recorded.</p>
      )}
      {incidents.map((inc) => (
        <div className="card" key={inc.incident_id}>
          <h2>
            {inc.robot_id} — {inc.summary}{" "}
            <span
              className={
                inc.severity === "ERROR"
                  ? "badge badge-error"
                  : inc.severity === "WARN"
                    ? "badge badge-warn"
                    : "badge badge-ok"
              }
            >
              {inc.severity}
            </span>
          </h2>
          <p className="incident-meta">
            {formatDateTime(inc.started_at)}
            {inc.ended_at && ` → ${formatDateTime(inc.ended_at)}`}
          </p>
          <ul className="timeline">
            {inc.events.map((e, i) => (
              <li key={i}>
                <time>{formatTime(e.timestamp)}</time>
                <strong>{e.event_type}</strong> — {e.message}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
