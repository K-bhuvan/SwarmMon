import type { Robot } from "../api/client";
import {
  collectSignalColumns,
  getSignalCell,
} from "../lib/fleetStatus";

interface SignalMatrixProps {
  robots: Robot[];
  onSelectRobot: (robotId: string) => void;
}

function cellClass(robot: Robot, signalId: string): string {
  if (!robot.online) return "matrix-cell-offline";
  const signal = getSignalCell(robot, signalId);
  if (!signal) return "matrix-cell-missing";
  if (signal.status === "OK") return "matrix-cell-ok";
  if (signal.status === "STALE") return "matrix-cell-warn";
  return "matrix-cell-error";
}

function cellLabel(robot: Robot, signalId: string): string {
  if (!robot.online) return "offline";
  const signal = getSignalCell(robot, signalId);
  if (!signal) return "—";
  return signal.status === "OK" ? "OK" : signal.status;
}

export function SignalMatrix({ robots, onSelectRobot }: SignalMatrixProps) {
  const columns = collectSignalColumns(robots);
  const heartbeatCol = "__heartbeat__";
  const allColumns = [...columns, heartbeatCol];

  return (
    <div className="signal-matrix-wrap">
      <table className="signal-matrix">
        <thead>
          <tr>
            <th className="matrix-sticky-col">Robot</th>
            {allColumns.map((col) => (
              <th key={col}>{col === heartbeatCol ? "heartbeat" : col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {robots.map((robot) => (
            <tr key={robot.robot_id}>
              <th className="matrix-sticky-col">
                <button
                  type="button"
                  className="matrix-robot-link"
                  onClick={() => onSelectRobot(robot.robot_id)}
                >
                  {robot.robot_id}
                </button>
              </th>
              {allColumns.map((col) => {
                if (col === heartbeatCol) {
                  const cls = robot.online ? "matrix-cell-ok" : "matrix-cell-offline";
                  return (
                    <td key={col}>
                      <span className={`matrix-cell ${cls}`} title={robot.online ? "online" : "offline"}>
                        {robot.online ? "●" : "○"}
                      </span>
                    </td>
                  );
                }
                const title = getSignalCell(robot, col)
                  ? `${col}: ${cellLabel(robot, col)}`
                  : `${col}: no data`;
                return (
                  <td key={col}>
                    <span
                      className={`matrix-cell ${cellClass(robot, col)}`}
                      title={title}
                    >
                      {cellLabel(robot, col) === "OK" ? "●" : cellLabel(robot, col) === "—" ? "—" : "◐"}
                    </span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="matrix-legend">
        <span><span className="matrix-cell matrix-cell-ok">●</span> OK</span>
        <span><span className="matrix-cell matrix-cell-warn">◐</span> Stale</span>
        <span><span className="matrix-cell matrix-cell-error">◐</span> Missing</span>
        <span><span className="matrix-cell matrix-cell-offline">○</span> Offline</span>
      </p>
    </div>
  );
}
