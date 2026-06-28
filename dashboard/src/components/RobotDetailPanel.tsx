import type { Robot } from "../api/client";
import { getHealthLabel, getRobotHealth } from "../lib/fleetStatus";
import { useTimezone } from "../theme/TimezoneContext";

function statusBadge(status: string) {
  const cls =
    status === "OK"
      ? "badge badge-ok"
      : status === "STALE" || status === "WARN"
        ? "badge badge-warn"
        : "badge badge-error";
  return <span className={cls}>{status}</span>;
}

interface RobotDetailPanelProps {
  robot: Robot;
  onClose: () => void;
}

export function RobotDetailPanel({ robot, onClose }: RobotDetailPanelProps) {
  const health = getRobotHealth(robot);
  const { formatDateTime } = useTimezone();

  return (
    <aside className="robot-detail-panel">
      <div className="robot-detail-header">
        <div>
          <h2>{robot.robot_id}</h2>
          <span className={`badge badge-${health === "ok" ? "ok" : health === "warn" ? "warn" : health === "offline" ? "offline" : "error"}`}>
            {robot.online ? getHealthLabel(health) : "OFFLINE"}
          </span>
        </div>
        <button type="button" className="panel-close" onClick={onClose} aria-label="Close">
          ×
        </button>
      </div>

      {robot.last_heartbeat && (
        <p className="robot-detail-meta">
          Last heartbeat: {formatDateTime(robot.last_heartbeat)}
        </p>
      )}

      {robot.signals.length > 0 && (
        <section className="robot-detail-section">
          <h3>Signals</h3>
          <table>
            <thead>
              <tr>
                <th>Signal</th>
                <th>Status</th>
                <th>Last seen (ms)</th>
                <th>Expected Hz</th>
              </tr>
            </thead>
            <tbody>
              {robot.signals.map((s) => (
                <tr key={s.signal_id}>
                  <td>{s.signal_id}</td>
                  <td>{statusBadge(s.status)}</td>
                  <td>{s.last_seen_ms_ago ?? "—"}</td>
                  <td>{s.expected_rate_hz ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {robot.components.length > 0 && (
        <section className="robot-detail-section">
          <h3>Components</h3>
          <table>
            <thead>
              <tr>
                <th>Component</th>
                <th>Type</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {robot.components.map((c) => (
                <tr key={c.component_id}>
                  <td>{c.component_id}</td>
                  <td>{c.component_type}</td>
                  <td>{statusBadge(c.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {robot.diagnostics.length > 0 && (
        <section className="robot-detail-section">
          <h3>Diagnostics</h3>
          <ul className="diag-list">
            {robot.diagnostics.map((d) => (
              <li key={d.name}>
                <strong>{d.name}</strong> {statusBadge(d.level)} — {d.message}
              </li>
            ))}
          </ul>
        </section>
      )}
    </aside>
  );
}
