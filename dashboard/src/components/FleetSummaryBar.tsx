import type { FleetSummary } from "../lib/fleetStatus";

interface FleetSummaryBarProps {
  summary: FleetSummary;
  scenarioRunId: string;
  runStatus?: string;
  apiConnected?: boolean;
}

type FleetMode = "live" | "offline" | "waiting" | "reconnecting" | "snapshot";

function fleetMode(
  summary: FleetSummary,
  runStatus: string | undefined,
  apiConnected: boolean,
): { mode: FleetMode; label: string } {
  if (runStatus && runStatus !== "running") {
    return { mode: "snapshot", label: "SNAPSHOT" };
  }
  if (!apiConnected) {
    return { mode: "reconnecting", label: "RECONNECTING" };
  }
  if (summary.total === 0) {
    return { mode: "waiting", label: "WAITING" };
  }
  if (summary.online === 0) {
    return { mode: "offline", label: "OFFLINE" };
  }
  return { mode: "live", label: "LIVE" };
}

export function FleetSummaryBar({
  summary,
  scenarioRunId,
  runStatus,
  apiConnected = true,
}: FleetSummaryBarProps) {
  const { mode, label } = fleetMode(summary, runStatus, apiConnected);
  const runCompleted = runStatus !== undefined && runStatus !== "running";

  return (
    <div className="fleet-summary">
      <div className="fleet-summary-meta">
        <span className="fleet-summary-title">
          Scenario {scenarioRunId}
          <span className={`fleet-mode-badge fleet-mode-${mode}`}>{label}</span>
        </span>
        <span className="fleet-summary-sub">
          {summary.online}/{summary.total} online
          {summary.staleSignals > 0 && ` · ${summary.staleSignals} stale signals`}
          {runCompleted && " · run completed"}
        </span>
      </div>
      <div className="fleet-summary-stats">
        <Stat label="OK" value={summary.ok} tone="ok" />
        <Stat label="DEGRADED" value={summary.degraded} tone="warn" />
        <Stat label="ERROR" value={summary.error} tone="error" />
        <Stat label="OFFLINE" value={summary.offline} tone="offline" />
        {summary.unknown > 0 && <Stat label="UNKNOWN" value={summary.unknown} tone="offline" />}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "ok" | "warn" | "error" | "offline";
}) {
  return (
    <div className={`fleet-stat fleet-stat-${tone}`}>
      <span className="fleet-stat-value">{value}</span>
      <span className="fleet-stat-label">{label}</span>
    </div>
  );
}
