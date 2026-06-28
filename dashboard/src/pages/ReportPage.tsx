import { useState } from "react";
import { getScenarioReport } from "../api/client";
import type { ScenarioReport } from "../api/client";

export default function ReportPage() {
  const [scenarioRunId, setScenarioRunId] = useState("run-ros2-live");
  const [report, setReport] = useState<ScenarioReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const data = await getScenarioReport(scenarioRunId);
      setReport(data);
    } catch (e) {
      setReport(null);
      setError(e instanceof Error ? e.message : "Failed to load report");
    }
  }

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
        <button type="button" className="btn-primary" onClick={load}>Load report</button>
      </div>
      {error && <p className="error">{error}</p>}
      {report && (
        <div className="card">
          <h2>
            {report.scenario_name}{" "}
            <span className={report.scenario_passed ? "badge badge-ok" : "badge badge-error"}>
              {report.scenario_passed ? "PASSED" : "FAILED"}
            </span>
          </h2>
          <table>
            <tbody>
              <tr><th>Simulator</th><td>{report.simulator}</td></tr>
              <tr><th>Robot profile</th><td>{report.robot_profile ?? "—"}</td></tr>
              <tr><th>Environment</th><td>{report.environment_profile ?? "—"}</td></tr>
              <tr><th>Robot count</th><td>{report.robot_count}</td></tr>
              <tr><th>Total incidents</th><td>{report.total_incidents}</td></tr>
              <tr><th>False offline count</th><td>{report.false_offline_count}</td></tr>
              <tr><th>Missed expected failures</th><td>{report.missed_expected_failures}</td></tr>
              <tr><th>Missing required signals</th><td>{report.missing_required_signals.join(", ") || "—"}</td></tr>
              <tr><th>Replay artifact</th><td>{report.replay_artifact_path ?? "—"}</td></tr>
            </tbody>
          </table>
          <p className="report-summary">{report.summary}</p>
        </div>
      )}
    </div>
  );
}
