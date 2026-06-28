import type { Robot, SignalState } from "../api/client";
import { parseApiTimestamp } from "./timezone";

export { parseApiTimestamp };

export type RobotHealth = "ok" | "warn" | "error" | "offline" | "unknown";

const HEALTH_RANK: Record<RobotHealth, number> = {
  error: 0,
  offline: 1,
  warn: 2,
  unknown: 3,
  ok: 4,
};

export function isDegraded(robot: Robot): boolean {
  const hasSignalIssue = robot.signals.some(
    (s) => s.status === "STALE" || s.status === "MISSING",
  );
  const hasDiagIssue = robot.diagnostics.some(
    (d) => d.level === "WARN" || d.level === "ERROR",
  );
  const hasComponentIssue = robot.components.some((c) => c.status !== "OK");
  return hasSignalIssue || hasDiagIssue || hasComponentIssue;
}

export function isOffline(robot: Robot): boolean {
  return !robot.online;
}

/** ros2_live agent heartbeats ~every 2s. Field fleets use API-provided max age (typically 45s). */
export const DEFAULT_LIVE_HEARTBEAT_MAX_AGE_MS = 10_000;

/** @deprecated use fleet.live_max_age_seconds from API */
export const LIVE_HEARTBEAT_MAX_AGE_MS = DEFAULT_LIVE_HEARTBEAT_MAX_AGE_MS;

export function withFreshOnline(
  robot: Robot,
  maxAgeMs: number,
  nowMs = Date.now(),
): Robot {
  const age = heartbeatAgeMs(robot, nowMs);
  if (age === null) {
    return { ...robot, online: false };
  }
  return { ...robot, online: age >= 0 && age <= maxAgeMs };
}

export function applyFleetFreshness(
  robots: Robot[],
  maxAgeMs: number,
  nowMs = Date.now(),
): Robot[] {
  return robots.map((r) => withFreshOnline(r, maxAgeMs, nowMs));
}

/** Merge registered roster with fleet telemetry (placeholders for never-seen robots). */
export function buildFleetDisplay(
  fleetRobots: Robot[],
  registered: Array<{ robot_id: string; scenario_run_id: string; last_heartbeat: string | null }>,
  scenarioRunId: string,
): Robot[] {
  const byId = new Map(fleetRobots.map((r) => [r.robot_id, r]));
  for (const reg of registered) {
    if (!byId.has(reg.robot_id)) {
      byId.set(reg.robot_id, {
        robot_id: reg.robot_id,
        scenario_run_id: scenarioRunId,
        online: false,
        last_heartbeat: reg.last_heartbeat,
        signals: [],
        components: [],
        diagnostics: [],
      });
    }
  }
  return [...byId.values()].sort((a, b) =>
    a.robot_id.localeCompare(b.robot_id, undefined, { numeric: true }),
  );
}

export function forceOffline(robots: Robot[]): Robot[] {
  return robots.map((r) => ({ ...r, online: false }));
}

export function heartbeatAgeMs(robot: Robot, nowMs = Date.now()): number | null {
  if (!robot.last_heartbeat) return null;
  const ts = parseApiTimestamp(robot.last_heartbeat);
  if (Number.isNaN(ts)) return null;
  return nowMs - ts;
}

export function isRobotLive(
  robot: Robot,
  maxAgeMs = DEFAULT_LIVE_HEARTBEAT_MAX_AGE_MS,
  nowMs = Date.now(),
): boolean {
  const fresh = withFreshOnline(robot, maxAgeMs, nowMs);
  return fresh.online;
}

export function filterLiveRobots(
  robots: Robot[],
  maxAgeMs = DEFAULT_LIVE_HEARTBEAT_MAX_AGE_MS,
  nowMs = Date.now(),
): Robot[] {
  return robots.filter((r) => isRobotLive(r, maxAgeMs, nowMs));
}

export function getRobotHealth(robot: Robot): RobotHealth {
  if (!robot.online) return "offline";
  if (robot.components.some((c) => c.status !== "OK")) return "error";
  if (robot.diagnostics.some((d) => d.level === "ERROR")) return "error";
  if (isDegraded(robot)) return "warn";
  if (!robot.last_heartbeat && robot.signals.length === 0) return "unknown";
  return "ok";
}

export function getHealthLabel(health: RobotHealth): string {
  switch (health) {
    case "ok":
      return "OK";
    case "warn":
      return "WARN";
    case "error":
      return "ERROR";
    case "offline":
      return "OFFLINE";
    case "unknown":
      return "UNKNOWN";
  }
}

export function getIssueSummary(robot: Robot): string | null {
  const health = getRobotHealth(robot);
  if (health === "offline") return "No heartbeat";
  if (health === "ok") return null;

  const stale = robot.signals.find((s) => s.status !== "OK");
  if (stale) return `${stale.signal_id} ${stale.status}`;

  const badComponent = robot.components.find((c) => c.status !== "OK");
  if (badComponent) return `${badComponent.component_id} ${badComponent.status}`;

  const badDiag = robot.diagnostics.find((d) => d.level === "WARN" || d.level === "ERROR");
  if (badDiag) return `${badDiag.name} ${badDiag.level}`;

  return null;
}

export function sortRobotsBySeverity(robots: Robot[]): Robot[] {
  return [...robots].sort((a, b) => {
    const diff = HEALTH_RANK[getRobotHealth(a)] - HEALTH_RANK[getRobotHealth(b)];
    if (diff !== 0) return diff;
    return a.robot_id.localeCompare(b.robot_id, undefined, { numeric: true });
  });
}

export interface FleetSummary {
  total: number;
  online: number;
  ok: number;
  warn: number;
  error: number;
  offline: number;
  unknown: number;
  degraded: number;
  staleSignals: number;
}

export function summarizeFleet(robots: Robot[]): FleetSummary {
  const summary: FleetSummary = {
    total: robots.length,
    online: 0,
    ok: 0,
    warn: 0,
    error: 0,
    offline: 0,
    unknown: 0,
    degraded: 0,
    staleSignals: 0,
  };

  for (const robot of robots) {
    if (robot.online) summary.online += 1;
    if (isDegraded(robot)) summary.degraded += 1;
    if (!robot.online) {
      summary.offline += 1;
    } else {
      const health = getRobotHealth(robot);
      summary[health] += 1;
    }
    summary.staleSignals += robot.signals.filter((s) => s.status !== "OK").length;
  }

  return summary;
}

export function collectSignalColumns(robots: Robot[]): string[] {
  const ids = new Set<string>();
  for (const robot of robots) {
    for (const s of robot.signals) {
      ids.add(s.signal_id);
    }
  }
  return [...ids].sort();
}

export function getSignalCell(robot: Robot, signalId: string): SignalState | null {
  return robot.signals.find((s) => s.signal_id === signalId) ?? null;
}

export type FleetFilter = "all" | "degraded" | "offline";

export function filterRobots(
  robots: Robot[],
  filter: FleetFilter,
  search: string,
): Robot[] {
  let result = robots;
  const q = search.trim().toLowerCase();

  if (q) {
    result = result.filter((r) => r.robot_id.toLowerCase().includes(q));
  }

  if (filter === "degraded") {
    result = result.filter((r) => isDegraded(r));
  } else if (filter === "offline") {
    result = result.filter((r) => isOffline(r));
  }

  return result;
}
