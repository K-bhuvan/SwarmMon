import type { Robot } from "../api/client";
import { getHealthLabel, getIssueSummary, getRobotHealth } from "../lib/fleetStatus";

interface RobotTileProps {
  robot: Robot;
  selected: boolean;
  onSelect: () => void;
}

export function RobotTile({ robot, selected, onSelect }: RobotTileProps) {
  const health = getRobotHealth(robot);
  const issue = getIssueSummary(robot);

  return (
    <button
      type="button"
      className={`robot-tile robot-tile-${health}${selected ? " robot-tile-selected" : ""}`}
      onClick={onSelect}
      aria-pressed={selected}
      aria-label={`${robot.robot_id} ${getHealthLabel(health)}`}
    >
      <span className="robot-tile-id">{robot.robot_id}</span>
      <span className={`robot-tile-dot robot-tile-dot-${health}`} aria-hidden />
      <span className="robot-tile-status">{getHealthLabel(health)}</span>
      {issue && <span className="robot-tile-issue">{issue}</span>}
    </button>
  );
}
