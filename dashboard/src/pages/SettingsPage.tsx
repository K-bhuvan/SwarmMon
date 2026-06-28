import { useCallback, useEffect, useState } from "react";
import {
  getFleetAlertSettings,
  getScenarioRuns,
  updateFleetAlertSettings,
} from "../api/client";
import type { FleetAlertSettings, ScenarioRun } from "../api/client";
import { DisplayPreferences } from "../components/DisplayPreferences";

function liveScenarioRuns(runs: ScenarioRun[]): ScenarioRun[] {
  return runs.filter((r) => r.status === "running");
}

export default function SettingsPage() {
  const [scenarioRuns, setScenarioRuns] = useState<ScenarioRun[]>([]);
  const [scenarioRunId, setScenarioRunId] = useState("");
  const [settings, setSettings] = useState<FleetAlertSettings | null>(null);
  const [email, setEmail] = useState("");
  const [offlineMinutes, setOfflineMinutes] = useState(5);
  const [alertsEnabled, setAlertsEnabled] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async (runId: string) => {
    if (!runId) {
      setSettings(null);
      return;
    }
    try {
      const data = await getFleetAlertSettings(runId);
      setSettings(data);
      setEmail(data.notify_email ?? "");
      setOfflineMinutes(data.offline_alert_minutes);
      setAlertsEnabled(data.alerts_enabled);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load alert settings");
    }
  }, []);

  useEffect(() => {
    getScenarioRuns()
      .then((runs) => {
        setScenarioRuns(runs);
        const live = liveScenarioRuns(runs);
        const id = live[0]?.scenario_run_id ?? "";
        setScenarioRunId(id);
        if (id) load(id);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load scenarios"));
  }, [load]);

  useEffect(() => {
    if (scenarioRunId) load(scenarioRunId);
  }, [scenarioRunId, load]);

  async function handleSaveAlerts(e: React.FormEvent) {
    e.preventDefault();
    if (!scenarioRunId) return;
    setSaving(true);
    setSaved(false);
    try {
      const data = await updateFleetAlertSettings(scenarioRunId, {
        notify_email: email.trim() || null,
        offline_alert_minutes: offlineMinutes,
        alerts_enabled: alertsEnabled,
      });
      setSettings(data);
      setSaved(true);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  const liveRuns = liveScenarioRuns(scenarioRuns);
  const selectedRunId =
    liveRuns.find((r) => r.scenario_run_id === scenarioRunId)?.scenario_run_id ??
    liveRuns[0]?.scenario_run_id ??
    "";

  return (
    <div className="settings-page">
      <header className="settings-page-header">
        <h2>Settings</h2>
        <p className="settings-intro">
          Profile, display, and fleet alert preferences. Stored locally in your browser unless
          noted otherwise.
        </p>
      </header>

      {error && <p className="error">{error}</p>}

      <section className="settings-section card" aria-labelledby="settings-display-heading">
        <h3 id="settings-display-heading">Profile &amp; display</h3>
        <DisplayPreferences />
      </section>

      <section className="settings-section card" aria-labelledby="settings-alerts-heading">
        <h3 id="settings-alerts-heading">Fleet alerts</h3>
        <p className="settings-section-intro">
          Email an operator when a robot stops reporting. Uses{" "}
          <a href="https://resend.com" target="_blank" rel="noreferrer">
            Resend
          </a>{" "}
          (free tier).
        </p>

        <form className="settings-form" onSubmit={handleSaveAlerts}>
          <label className="settings-field">
            <span className="settings-field-label">Fleet / scenario</span>
            {liveRuns.length > 0 ? (
              <select
                value={selectedRunId}
                onChange={(e) => setScenarioRunId(e.target.value)}
              >
                {liveRuns.map((run) => (
                  <option key={run.scenario_run_id} value={run.scenario_run_id}>
                    {run.scenario_run_id}
                  </option>
                ))}
              </select>
            ) : (
              <span className="fleet-no-live">No running fleet</span>
            )}
          </label>

          <label className="settings-field">
            <span className="settings-field-label">Alert email</span>
            <input
              type="email"
              placeholder="mike@farm.example"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>

          <label className="settings-field">
            <span className="settings-field-label">Offline after (minutes)</span>
            <input
              type="number"
              min={1}
              max={120}
              value={offlineMinutes}
              onChange={(e) => setOfflineMinutes(Number(e.target.value))}
            />
          </label>

          <label className="settings-checkbox">
            <input
              type="checkbox"
              checked={alertsEnabled}
              onChange={(e) => setAlertsEnabled(e.target.checked)}
            />
            Email alerts enabled
          </label>

          {settings && !settings.resend_configured && (
            <p className="settings-warn">
              Backend has no <code>SWARMMON_RESEND_API_KEY</code> — alerts will not send until
              configured on the server.
            </p>
          )}

          <button type="submit" className="btn-primary" disabled={saving || !scenarioRunId}>
            {saving ? "Saving…" : "Save alert settings"}
          </button>
          {saved && <p className="settings-saved">Alert settings saved.</p>}
        </form>
      </section>
    </div>
  );
}
