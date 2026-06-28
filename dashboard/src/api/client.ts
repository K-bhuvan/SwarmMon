export interface SignalState {
  signal_id: string;
  signal_type: string;
  message_type: string | null;
  expected_rate_hz: number | null;
  last_seen_ms_ago: number | null;
  status: "OK" | "STALE" | "MISSING";
  last_updated: string | null;
}

export interface ComponentState {
  component_id: string;
  component_type: string;
  status: "OK" | "MISSING" | "UNHEALTHY";
  last_updated: string | null;
}

export interface Robot {
  robot_id: string;
  scenario_run_id: string | null;
  online: boolean;
  last_heartbeat: string | null;
  signals: SignalState[];
  components: ComponentState[];
  diagnostics: Array<{
    name: string;
    level: string;
    message: string;
    timestamp: string;
  }>;
}

export interface ScenarioRun {
  scenario_run_id: string;
  scenario_name: string;
  simulator: string;
  robot_profile: string | null;
  environment_profile: string | null;
  robot_count: number;
  status: "running" | "completed" | string;
  started_at: string;
  completed_at: string | null;
  replay_artifact_path: string | null;
}

export interface FleetResponse {
  robots: Robot[];
  scenario_run_id: string | null;
  live_max_age_seconds: number;
  simulator: string | null;
}

export interface IncidentTimelineEntry {
  timestamp: string;
  event_type: string;
  message: string;
}

export interface Incident {
  incident_id: string;
  scenario_run_id: string;
  robot_id: string;
  severity: "INFO" | "WARN" | "ERROR";
  started_at: string;
  ended_at: string | null;
  summary: string;
  events: IncidentTimelineEntry[];
}

export interface ScenarioReport {
  scenario_run_id: string;
  scenario_name: string;
  simulator: string;
  robot_profile: string | null;
  environment_profile: string | null;
  robot_count: number;
  total_incidents: number;
  incident_severity_breakdown: Record<string, number>;
  detection_latency_seconds: number[];
  missed_expected_failures: number;
  false_offline_count: number;
  missing_required_signals: string[];
  replay_artifact_path: string | null;
  scenario_passed: boolean;
  summary: string;
}

const API_BASE = import.meta.env.VITE_API_URL ?? "";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(detail || `${res.status} ${res.statusText}`);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export interface FleetAlertSettings {
  scenario_run_id: string;
  notify_email: string | null;
  offline_alert_minutes: number;
  alerts_enabled: boolean;
  resend_configured: boolean;
}

export interface RegisteredRobot {
  robot_id: string;
  scenario_run_id: string;
  label: string | null;
  registered_at: string;
  status: "pending" | "live" | "offline" | string;
  last_heartbeat: string | null;
  online: boolean;
}

export function getFleetAlertSettings(scenarioRunId: string): Promise<FleetAlertSettings> {
  return fetchJson(`/api/v1/fleet/settings/${encodeURIComponent(scenarioRunId)}`);
}

export function updateFleetAlertSettings(
  scenarioRunId: string,
  body: Partial<Pick<FleetAlertSettings, "notify_email" | "offline_alert_minutes" | "alerts_enabled">>,
): Promise<FleetAlertSettings> {
  return fetchJson(`/api/v1/fleet/settings/${encodeURIComponent(scenarioRunId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getRegisteredRobots(scenarioRunId: string): Promise<RegisteredRobot[]> {
  return fetchJson(`/api/v1/fleet/robots/${encodeURIComponent(scenarioRunId)}`);
}

export function registerRobot(
  scenarioRunId: string,
  body: { robot_id: string; label?: string },
): Promise<RegisteredRobot> {
  return fetchJson(`/api/v1/fleet/robots/${encodeURIComponent(scenarioRunId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function fetchJsonGet<T>(path: string): Promise<T> {
  return fetchJson(path);
}

export function getScenarioRuns(): Promise<ScenarioRun[]> {
  return fetchJsonGet("/api/v1/scenarios/runs");
}

export function getFleet(scenarioRunId?: string, live = true): Promise<FleetResponse> {
  const params = new URLSearchParams();
  if (scenarioRunId) params.set("scenario_run_id", scenarioRunId);
  if (live) params.set("live", "true");
  const q = params.size ? `?${params.toString()}` : "";
  return fetchJsonGet(`/api/v1/fleet${q}`);
}

export function getIncidents(scenarioRunId?: string): Promise<Incident[]> {
  const q = scenarioRunId ? `?scenario_run_id=${encodeURIComponent(scenarioRunId)}` : "";
  return fetchJsonGet(`/api/v1/incidents${q}`);
}

export function getScenarioReport(scenarioRunId: string): Promise<ScenarioReport> {
  return fetchJsonGet(`/api/v1/scenarios/runs/${encodeURIComponent(scenarioRunId)}/report`);
}
