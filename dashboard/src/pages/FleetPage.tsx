import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  getFleet,
  getRegisteredRobots,
  getScenarioRuns,
  registerRobot,
} from "../api/client";
import type { FleetResponse, RegisteredRobot, Robot, ScenarioRun } from "../api/client";
import { FleetSummaryBar } from "../components/FleetSummaryBar";
import { RobotDetailPanel } from "../components/RobotDetailPanel";
import { RobotTile } from "../components/RobotTile";
import { SignalMatrix } from "../components/SignalMatrix";
import {
  applyFleetFreshness,
  buildFleetDisplay,
  DEFAULT_LIVE_HEARTBEAT_MAX_AGE_MS,
  filterLiveRobots,
  filterRobots,
  forceOffline,
  isDegraded,
  isOffline,
  sortRobotsBySeverity,
  summarizeFleet,
  type FleetFilter,
} from "../lib/fleetStatus";
import { useTimezone } from "../theme/TimezoneContext";

type FleetView = "grid" | "matrix";

const LIVE_POLL_MS = 2_000;

function liveScenarioRuns(runs: ScenarioRun[]): ScenarioRun[] {
  return runs.filter((r) => r.status === "running");
}

export default function FleetPage() {
  const [scenarioRuns, setScenarioRuns] = useState<ScenarioRun[]>([]);
  const [scenarioRunId, setScenarioRunId] = useState("");
  const [fleet, setFleet] = useState<FleetResponse | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [apiConnected, setApiConnected] = useState(true);
  const [manualSyncing, setManualSyncing] = useState(false);
  const [filter, setFilter] = useState<FleetFilter>("all");
  const [search, setSearch] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const [view, setView] = useState<FleetView>("grid");
  const [selectedRobotId, setSelectedRobotId] = useState<string | null>(null);
  const [streamEnded, setStreamEnded] = useState(false);
  const [tickMs, setTickMs] = useState(() => Date.now());
  const [registeredRobots, setRegisteredRobots] = useState<RegisteredRobot[]>([]);
  const [newRobotId, setNewRobotId] = useState("");
  const [newRobotLabel, setNewRobotLabel] = useState("");
  const [addRobotError, setAddRobotError] = useState<string | null>(null);
  const [addingRobot, setAddingRobot] = useState(false);
  const { formatDateTime } = useTimezone();

  const lastFleetRef = useRef<FleetResponse | null>(null);
  const lastRegisteredRef = useRef<RegisteredRobot[]>([]);

  const searchExpanded = searchOpen || search.trim().length > 0;

  function openSearch() {
    setSearchOpen(true);
    requestAnimationFrame(() => searchInputRef.current?.focus());
  }

  function closeSearchIfEmpty() {
    if (!search.trim()) {
      setSearchOpen(false);
    }
  }

  const liveRuns = useMemo(
    () => liveScenarioRuns(scenarioRuns),
    [scenarioRuns],
  );

  const selectedRunId = useMemo(() => {
    if (liveRuns.length === 0) return "";
    return (
      liveRuns.find((r) => r.scenario_run_id === scenarioRunId)?.scenario_run_id ??
      liveRuns[0].scenario_run_id
    );
  }, [liveRuns, scenarioRunId]);

  const activeRun = useMemo(
    () => liveRuns.find((r) => r.scenario_run_id === scenarioRunId) ?? null,
    [liveRuns, scenarioRunId],
  );

  const isFieldFleet = activeRun?.simulator === "field_fleet";

  const liveMaxAgeMs = useMemo(
    () => (fleet?.live_max_age_seconds ?? DEFAULT_LIVE_HEARTBEAT_MAX_AGE_MS / 1000) * 1000,
    [fleet?.live_max_age_seconds],
  );

  const displayRobots = useMemo(() => {
    const merged = buildFleetDisplay(
      fleet?.robots ?? [],
      registeredRobots,
      scenarioRunId,
    );
    let robots = applyFleetFreshness(merged, liveMaxAgeMs, tickMs);
    if (!apiConnected) {
      robots = forceOffline(robots);
    }
    return robots;
  }, [fleet?.robots, registeredRobots, scenarioRunId, liveMaxAgeMs, tickMs, apiConnected]);

  const syncStatus = useMemo(() => {
    if (!apiConnected) {
      return { label: "Reconnecting…", className: "fleet-sync-reconnect" };
    }
    if (displayRobots.length === 0) {
      return { label: "Waiting", className: "fleet-sync-waiting" };
    }
    const onlineCount = displayRobots.filter((r) => r.online).length;
    if (onlineCount === 0) {
      return { label: "Offline", className: "fleet-sync-offline" };
    }
    return { label: "Live", className: "fleet-sync-live" };
  }, [apiConnected, displayRobots]);

  useEffect(() => {
    const id = setInterval(() => setTickMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const syncFleet = useCallback(async (options?: { manual?: boolean }) => {
    if (options?.manual) {
      setManualSyncing(true);
    }
    try {
      const runs = await getScenarioRuns();
      setScenarioRuns(runs);
      setApiConnected(true);

      const live = liveScenarioRuns(runs);
      const runId =
        live.find((r) => r.scenario_run_id === scenarioRunId)?.scenario_run_id ??
        live[0]?.scenario_run_id ??
        "";

      if (!runId) {
        setScenarioRunId("");
        setFleet(null);
        lastFleetRef.current = null;
        setRegisteredRobots([]);
        lastRegisteredRef.current = [];
        setStreamEnded(false);
        setLoaded(true);
        return;
      }

      if (runId !== scenarioRunId) {
        setScenarioRunId(runId);
        setSelectedRobotId(null);
      }

      const [data, registered] = await Promise.all([
        getFleet(runId, false),
        getRegisteredRobots(runId),
      ]);

      lastFleetRef.current = data;
      lastRegisteredRef.current = registered;
      setFleet(data);
      setRegisteredRobots(registered);

      const maxAgeMs = (data.live_max_age_seconds ?? DEFAULT_LIVE_HEARTBEAT_MAX_AGE_MS / 1000) * 1000;
      const isField = runs.find((r) => r.scenario_run_id === runId)?.simulator === "field_fleet";
      const fresh = filterLiveRobots(data.robots, maxAgeMs, Date.now());
      setStreamEnded(!isField && data.robots.length > 0 && fresh.length === 0);
      setLoaded(true);
    } catch {
      setApiConnected(false);
      if (lastFleetRef.current) {
        setFleet(lastFleetRef.current);
      }
      if (lastRegisteredRef.current.length > 0) {
        setRegisteredRobots(lastRegisteredRef.current);
      }
      setLoaded(true);
    } finally {
      if (options?.manual) {
        setManualSyncing(false);
      }
    }
  }, [scenarioRunId]);

  useEffect(() => {
    syncFleet();
    const id = setInterval(() => syncFleet(), LIVE_POLL_MS);
    return () => clearInterval(id);
  }, [syncFleet]);

  useEffect(() => {
    if (selectedRobotId && !displayRobots.some((r) => r.robot_id === selectedRobotId)) {
      setSelectedRobotId(null);
    }
  }, [displayRobots, selectedRobotId]);

  const robots = useMemo(() => {
    const filtered = filterRobots(displayRobots, filter, search);
    return sortRobotsBySeverity(filtered);
  }, [displayRobots, filter, search]);

  const summary = useMemo(() => summarizeFleet(displayRobots), [displayRobots]);

  const filterCounts = useMemo(() => {
    return {
      degraded: displayRobots.filter(isDegraded).length,
      offline: displayRobots.filter(isOffline).length,
    };
  }, [displayRobots]);

  const selectedRobot: Robot | null = useMemo(() => {
    if (!selectedRobotId) return null;
    return displayRobots.find((r) => r.robot_id === selectedRobotId) ?? null;
  }, [selectedRobotId, displayRobots]);

  const hasLiveScenario = liveRuns.length > 0 && !!activeRun;
  const showLiveGrid =
    hasLiveScenario && displayRobots.length > 0 && (isFieldFleet || !streamEnded);
  const waitingForTelemetry =
    hasLiveScenario && displayRobots.length === 0 && !streamEnded && registeredRobots.length === 0;

  async function handleAddRobot(e: React.FormEvent) {
    e.preventDefault();
    if (!scenarioRunId || !newRobotId.trim()) return;
    setAddingRobot(true);
    setAddRobotError(null);
    try {
      await registerRobot(scenarioRunId, {
        robot_id: newRobotId.trim(),
        label: newRobotLabel.trim() || undefined,
      });
      setNewRobotId("");
      setNewRobotLabel("");
      await syncFleet();
    } catch (err) {
      setAddRobotError(err instanceof Error ? err.message : "Failed to add robot");
    } finally {
      setAddingRobot(false);
    }
  }

  return (
    <div className="fleet-page">
      <div className="controls fleet-controls">
        <label>
          Live scenario{" "}
          {liveRuns.length > 0 ? (
            <select
              value={selectedRunId}
              onChange={(e) => {
                setScenarioRunId(e.target.value);
                setSelectedRobotId(null);
              }}
            >
              {liveRuns.map((run) => (
                <option key={run.scenario_run_id} value={run.scenario_run_id}>
                  {run.scenario_run_id}
                </option>
              ))}
            </select>
          ) : (
            <span className="fleet-no-live">none running</span>
          )}
        </label>
        <div
          className={`fleet-search-wrap${searchExpanded ? " fleet-search-open" : ""}`}
        >
          <label className="fleet-search-ring">
            <span className="fleet-search-icon" aria-hidden>
              <svg viewBox="0 0 24 24" width={16} height={16} focusable="false">
                <path
                  fill="currentColor"
                  d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5Zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14Z"
                />
              </svg>
            </span>
            <input
              ref={searchInputRef}
              className="fleet-search"
              type="search"
              placeholder="Search…"
              value={search}
              aria-label="Search robot ID"
              onChange={(e) => setSearch(e.target.value)}
              onFocus={() => setSearchOpen(true)}
              onBlur={closeSearchIfEmpty}
              onKeyDown={(e) => {
                if (e.key === "Escape") {
                  setSearch("");
                  setSearchOpen(false);
                  searchInputRef.current?.blur();
                }
              }}
            />
          </label>
          {!searchExpanded && (
            <button
              type="button"
              className="fleet-search-hit"
              aria-label="Search robots"
              onClick={openSearch}
            />
          )}
        </div>

        <div className="fleet-controls-divider" aria-hidden />

        <div className="fleet-control-group fleet-filter-group">
          <span className="fleet-control-group-label" id="fleet-filter-label">
            Filter
          </span>
          <div
            className="filter-chips"
            role="group"
            aria-labelledby="fleet-filter-label"
          >
            {(["all", "degraded", "offline"] as const).map((f) => (
              <button
                key={f}
                type="button"
                className={`chip${filter === f ? " chip-active" : ""}`}
                onClick={() => setFilter(f)}
              >
                {f === "all"
                  ? `All (${displayRobots.length})`
                  : f === "degraded"
                    ? `Degraded (${filterCounts.degraded})`
                    : `Offline (${filterCounts.offline})`}
              </button>
            ))}
          </div>
        </div>

        <div className="fleet-controls-divider" aria-hidden />

        <div className="fleet-control-group fleet-view-group">
          <span className="fleet-control-group-label" id="fleet-view-label">
            View
          </span>
          <div
            className="view-toggle"
            role="group"
            aria-labelledby="fleet-view-label"
          >
            <button
              type="button"
              className={`view-chip${view === "grid" ? " view-chip-active" : ""}`}
              onClick={() => setView("grid")}
            >
              Grid
            </button>
            <button
              type="button"
              className={`view-chip${view === "matrix" ? " view-chip-active" : ""}`}
              onClick={() => setView("matrix")}
            >
              Matrix
            </button>
          </div>
        </div>

        <div className="fleet-sync-controls">
          {hasLiveScenario && (
            <span
              className={`fleet-sync-status ${syncStatus.className}`}
              title={
                apiConnected
                  ? "Auto-updating every 2 seconds"
                  : "Using last known fleet data until the backend responds"
              }
            >
              <span className="fleet-sync-dot" aria-hidden />
              {syncStatus.label}
            </span>
          )}
          <button
            type="button"
            className={`fleet-refresh-btn${manualSyncing ? " fleet-refresh-btn-syncing" : ""}`}
            onClick={() => syncFleet({ manual: true })}
            disabled={manualSyncing}
            aria-busy={manualSyncing}
          >
            Refresh
          </button>
        </div>
      </div>

      {liveRuns.length === 0 && loaded && (
        <p className="empty-hint">
          No live fleet running.
          <br />
          Mike field fleet: <code>./scripts/onboard_field_fleet.sh</code> then{" "}
          <code>conda deactivate && ./scripts/ros2_mike_fleet.sh --dev</code>
          <br />
          ROS agent dev: <code>conda deactivate && ./scripts/ros2_live.sh</code>
        </p>
      )}

      {hasLiveScenario && (
        <section className="fleet-roster">
          <div className="fleet-roster-header">
            <h3>Fleet robots ({displayRobots.length || registeredRobots.length})</h3>
            {!isFieldFleet && (
              <form className="add-robot-form" onSubmit={handleAddRobot}>
                <input
                  type="text"
                  placeholder="Robot ID (e.g. robot-01)"
                  value={newRobotId}
                  onChange={(e) => setNewRobotId(e.target.value)}
                />
                <input
                  type="text"
                  placeholder="Label (optional)"
                  value={newRobotLabel}
                  onChange={(e) => setNewRobotLabel(e.target.value)}
                />
                <button type="submit" disabled={addingRobot || !newRobotId.trim()}>
                  {addingRobot ? "Adding…" : "Add robot"}
                </button>
              </form>
            )}
          </div>
          {addRobotError && <p className="error">{addRobotError}</p>}
          {displayRobots.length > 0 ? (
            <ul className="fleet-roster-list">
              {displayRobots.map((robot) => {
                const reg = registeredRobots.find((x) => x.robot_id === robot.robot_id);
                const status = robot.online ? "live" : robot.last_heartbeat ? "offline" : "pending";
                return (
                  <li
                    key={robot.robot_id}
                    className={`fleet-roster-item fleet-roster-${status}`}
                  >
                    <span className="fleet-roster-id">{reg?.label ?? robot.robot_id}</span>
                    <span className="fleet-roster-meta">
                      <code>{robot.robot_id}</code> · {status.toUpperCase()}
                      {robot.last_heartbeat &&
                        ` · last seen ${formatDateTime(robot.last_heartbeat)}`}
                    </span>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="empty-hint">
              No robots yet — run{" "}
              <code>conda deactivate && ./scripts/ros2_mike_fleet.sh --dev</code> after
              onboarding. Robots auto-register from <code>/swarmmon/fleet/status</code>.
            </p>
          )}
        </section>
      )}

      {streamEnded && liveRuns.length > 0 && !isFieldFleet && (
        <p className="empty-hint">
          Live stream ended (agent stopped or Ctrl+C). Restart:{" "}
          <code>conda deactivate && ./scripts/ros2_live.sh</code>
        </p>
      )}

      {showLiveGrid && activeRun && (
        <FleetSummaryBar
          summary={summary}
          scenarioRunId={scenarioRunId}
          runStatus={activeRun.status}
          apiConnected={apiConnected}
        />
      )}

      {waitingForTelemetry && (
        <p className="empty-hint">
          Waiting for ROS fleet status on <strong>{scenarioRunId}</strong>. Run:{" "}
          <code>conda deactivate && ./scripts/ros2_mike_fleet.sh --dev</code>
        </p>
      )}

      {showLiveGrid && robots.length === 0 && (
        <p className="empty-hint">No robots match the current filter.</p>
      )}

      {showLiveGrid && robots.length > 0 && (
        <div className={`fleet-layout${selectedRobot ? " fleet-layout-split" : ""}`}>
          <div className="fleet-main">
            {view === "grid" ? (
              <div className="robot-grid" role="list">
                {robots.map((robot) => (
                  <RobotTile
                    key={robot.robot_id}
                    robot={robot}
                    selected={selectedRobotId === robot.robot_id}
                    onSelect={() =>
                      setSelectedRobotId((id) =>
                        id === robot.robot_id ? null : robot.robot_id,
                      )
                    }
                  />
                ))}
              </div>
            ) : (
              <SignalMatrix
                robots={robots}
                onSelectRobot={(id) => setSelectedRobotId(id)}
              />
            )}
          </div>
          {selectedRobot && (
            <RobotDetailPanel
              robot={selectedRobot}
              onClose={() => setSelectedRobotId(null)}
            />
          )}
        </div>
      )}
    </div>
  );
}
