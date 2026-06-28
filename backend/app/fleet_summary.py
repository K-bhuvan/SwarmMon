from __future__ import annotations

from app.schemas import ComponentStatus, DiagnosticLevel, RobotResponse, SignalStatus


def robot_health(robot: RobotResponse) -> str:
    if not robot.online:
        return "offline"
    if any(c.status != ComponentStatus.OK for c in robot.components):
        return "error"
    if any(d.level == DiagnosticLevel.ERROR for d in robot.diagnostics):
        return "error"
    if any(s.status in (SignalStatus.STALE, SignalStatus.MISSING) for s in robot.signals):
        return "warn"
    if any(d.level == DiagnosticLevel.WARN for d in robot.diagnostics):
        return "warn"
    if not robot.last_heartbeat and not robot.signals:
        return "unknown"
    return "ok"


def summarize_robots(robots: list[RobotResponse]) -> dict[str, int]:
    summary = {
        "total": len(robots),
        "online": 0,
        "ok": 0,
        "warn": 0,
        "error": 0,
        "offline": 0,
        "unknown": 0,
        "stale_signals": 0,
    }
    for robot in robots:
        if robot.online:
            summary["online"] += 1
        health = robot_health(robot)
        summary[health] += 1
        summary["stale_signals"] += sum(
            1 for s in robot.signals if s.status != SignalStatus.OK
        )
    return summary
