from __future__ import annotations

import html
import logging
from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session, select

from app.config import settings
from app.models import (
    AlertNotificationState,
    FleetAlertSettings,
    RegisteredRobot,
    RobotState,
    ScenarioRun,
)
from app.resend_client import ResendError, send_email
from app.time_utils import ensure_utc, is_older_than, utc_now

logger = logging.getLogger(__name__)


@dataclass
class _OfflineAlert:
    robot_id: str
    label: str | None
    reason: str
    last_seen: datetime | None
    alert_state: AlertNotificationState


@dataclass
class _RecoveryAlert:
    robot_id: str
    label: str | None
    alert_state: AlertNotificationState


def _get_or_create_alert_state(
    session: Session, scenario_run_id: str, robot_id: str
) -> AlertNotificationState:
    stmt = select(AlertNotificationState).where(
        AlertNotificationState.scenario_run_id == scenario_run_id,
        AlertNotificationState.robot_id == robot_id,
    )
    row = session.exec(stmt).first()
    if row is None:
        row = AlertNotificationState(
            scenario_run_id=scenario_run_id,
            robot_id=robot_id,
        )
        session.add(row)
        session.flush()
    return row


def _robot_state(
    session: Session, scenario_run_id: str, robot_id: str
) -> RobotState | None:
    return session.exec(
        select(RobotState).where(
            RobotState.scenario_run_id == scenario_run_id,
            RobotState.robot_id == robot_id,
        )
    ).first()


def _is_robot_offline(
    state: RobotState | None,
    *,
    offline_minutes: int,
) -> bool:
    if state is None or state.last_heartbeat is None:
        return False
    return is_older_than(state.last_heartbeat, offline_minutes * 60)


def _is_never_connected(
    registered: RegisteredRobot,
    state: RobotState | None,
    *,
    offline_minutes: int,
) -> bool:
    if state is not None and state.last_heartbeat is not None:
        return False
    return is_older_than(registered.registered_at, offline_minutes * 60)


def _format_ts(value: datetime | None) -> str:
    if value is None:
        return "unknown"
    return ensure_utc(value).strftime("%Y-%m-%d %H:%M UTC")


def _display_name(label: str | None, robot_id: str) -> str:
    return label or robot_id


def _robot_table_rows(
    entries: list[tuple[str, str | None, str, datetime | None]],
) -> str:
    rows = []
    for robot_id, label, reason, last_seen in entries:
        name = html.escape(_display_name(label, robot_id))
        rows.append(
            "<tr>"
            f"<td><strong>{name}</strong></td>"
            f"<td><code>{html.escape(robot_id)}</code></td>"
            f"<td>{html.escape(reason)}</td>"
            f"<td>{html.escape(_format_ts(last_seen))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _send_batched_offline_email(
    *,
    to: str,
    scenario_run_id: str,
    entries: list[tuple[str, str | None, str, datetime | None]],
) -> None:
    count = len(entries)
    if count == 1:
        robot_id, label, reason, last_seen = entries[0]
        name = _display_name(label, robot_id)
        subject = f"[SwarmMon] {name} offline — {scenario_run_id}"
        body = (
            f"<p><strong>{html.escape(name)}</strong> (<code>{html.escape(robot_id)}</code>) "
            f"is offline in fleet <strong>{html.escape(scenario_run_id)}</strong>.</p>"
            f"<p>{html.escape(reason)}</p>"
            f"<p>Last heartbeat: {html.escape(_format_ts(last_seen))}</p>"
        )
    else:
        subject = f"[SwarmMon] {count} drones offline — {scenario_run_id}"
        body = (
            f"<p><strong>{count} drones</strong> are offline in fleet "
            f"<strong>{html.escape(scenario_run_id)}</strong>.</p>"
            "<table border=\"1\" cellpadding=\"6\" cellspacing=\"0\" "
            'style="border-collapse:collapse">'
            "<thead><tr>"
            "<th>Drone</th><th>ID</th><th>Reason</th><th>Last heartbeat</th>"
            "</tr></thead>"
            f"<tbody>{_robot_table_rows(entries)}</tbody>"
            "</table>"
        )

    send_email(
        to=to,
        subject=subject,
        html=f"{body}<p>Open your SwarmMon dashboard for details.</p>",
    )


def _send_batched_recovery_email(
    *,
    to: str,
    scenario_run_id: str,
    entries: list[tuple[str, str | None]],
) -> None:
    count = len(entries)
    if count == 1:
        robot_id, label = entries[0]
        name = _display_name(label, robot_id)
        subject = f"[SwarmMon] {name} back online — {scenario_run_id}"
        body = (
            f"<p><strong>{html.escape(name)}</strong> (<code>{html.escape(robot_id)}</code>) "
            f"is reporting again in fleet <strong>{html.escape(scenario_run_id)}</strong>.</p>"
        )
    else:
        subject = f"[SwarmMon] {count} drones back online — {scenario_run_id}"
        items = "".join(
            f"<li><strong>{html.escape(_display_name(label, robot_id))}</strong> "
            f"(<code>{html.escape(robot_id)}</code>)</li>"
            for robot_id, label in entries
        )
        body = (
            f"<p><strong>{count} drones</strong> are reporting again in fleet "
            f"<strong>{html.escape(scenario_run_id)}</strong>:</p>"
            f"<ul>{items}</ul>"
        )

    send_email(to=to, subject=subject, html=body)


def process_fleet_alerts(session: Session) -> int:
    """Check registered robots and send offline/recovery emails. Returns emails sent."""
    if not settings.resend_api_key:
        return 0

    sent = 0
    fleet_settings = session.exec(select(FleetAlertSettings)).all()
    for cfg in fleet_settings:
        if not cfg.alerts_enabled or not cfg.notify_email:
            continue

        run = session.get(ScenarioRun, cfg.scenario_run_id)
        if run is None or run.status != "running":
            continue

        registered = session.exec(
            select(RegisteredRobot).where(
                RegisteredRobot.scenario_run_id == cfg.scenario_run_id
            )
        ).all()

        targets: list[tuple[str, str | None]] = [
            (r.robot_id, r.label) for r in registered
        ]
        if not targets:
            states = session.exec(
                select(RobotState).where(
                    RobotState.scenario_run_id == cfg.scenario_run_id
                )
            ).all()
            targets = [(s.robot_id, None) for s in states]

        offline_pending: list[_OfflineAlert] = []
        recovery_pending: list[_RecoveryAlert] = []

        for robot_id, label in targets:
            reg = next(
                (r for r in registered if r.robot_id == robot_id),
                None,
            )
            state = _robot_state(session, cfg.scenario_run_id, robot_id)
            alert_state = _get_or_create_alert_state(
                session, cfg.scenario_run_id, robot_id
            )

            never_connected = (
                reg is not None
                and _is_never_connected(
                    reg, state, offline_minutes=cfg.offline_alert_minutes
                )
            )
            offline = _is_robot_offline(
                state, offline_minutes=cfg.offline_alert_minutes
            )
            is_live = (
                state is not None
                and state.last_heartbeat is not None
                and not is_older_than(
                    state.last_heartbeat, cfg.offline_alert_minutes * 60
                )
            )

            if (offline or never_connected) and not alert_state.offline_alert_sent:
                reason = (
                    "Never connected since registration."
                    if never_connected
                    else f"No heartbeat for more than {cfg.offline_alert_minutes} minutes."
                )
                offline_pending.append(
                    _OfflineAlert(
                        robot_id=robot_id,
                        label=label,
                        reason=reason,
                        last_seen=state.last_heartbeat if state else None,
                        alert_state=alert_state,
                    )
                )
            elif is_live and alert_state.offline_alert_sent:
                recovery_pending.append(
                    _RecoveryAlert(
                        robot_id=robot_id,
                        label=label,
                        alert_state=alert_state,
                    )
                )

        now = utc_now().replace(tzinfo=None)

        if offline_pending:
            try:
                _send_batched_offline_email(
                    to=cfg.notify_email,
                    scenario_run_id=cfg.scenario_run_id,
                    entries=[
                        (a.robot_id, a.label, a.reason, a.last_seen)
                        for a in offline_pending
                    ],
                )
                for alert in offline_pending:
                    alert.alert_state.offline_alert_sent = True
                    alert.alert_state.last_offline_email_at = now
                    session.add(alert.alert_state)
                sent += 1
            except ResendError as exc:
                logger.warning(
                    "Offline alert email failed for fleet %s: %s",
                    cfg.scenario_run_id,
                    exc,
                )

        if recovery_pending:
            try:
                _send_batched_recovery_email(
                    to=cfg.notify_email,
                    scenario_run_id=cfg.scenario_run_id,
                    entries=[(a.robot_id, a.label) for a in recovery_pending],
                )
                for alert in recovery_pending:
                    alert.alert_state.offline_alert_sent = False
                    alert.alert_state.last_recovery_email_at = now
                    session.add(alert.alert_state)
                sent += 1
            except ResendError as exc:
                logger.warning(
                    "Recovery alert email failed for fleet %s: %s",
                    cfg.scenario_run_id,
                    exc,
                )

    if sent:
        session.commit()
    return sent
