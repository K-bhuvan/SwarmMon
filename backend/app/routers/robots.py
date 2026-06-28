from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.database import get_session
from app.fleet_summary import summarize_robots
from app.services import build_fleet_response, build_robot_response
from app.schemas import FleetResponse, FleetSummaryResponse, RobotResponse

router = APIRouter(prefix="/api/v1", tags=["robots"])


@router.get("/fleet", response_model=FleetResponse)
def get_fleet(
    scenario_run_id: str | None = None,
    live: bool = False,
    session: Session = Depends(get_session),
) -> FleetResponse:
    return build_fleet_response(session, scenario_run_id, live=live)


@router.get("/fleet/summary", response_model=FleetSummaryResponse)
def get_fleet_summary(
    scenario_run_id: str | None = None,
    session: Session = Depends(get_session),
) -> FleetSummaryResponse:
    fleet = build_fleet_response(session, scenario_run_id)
    counts = summarize_robots(fleet.robots)
    return FleetSummaryResponse(scenario_run_id=scenario_run_id, **counts)


@router.get("/robots/{robot_id}", response_model=RobotResponse)
def get_robot(
    robot_id: str,
    scenario_run_id: str,
    session: Session = Depends(get_session),
) -> RobotResponse:
    response = build_robot_response(session, robot_id, scenario_run_id)
    if response.last_heartbeat is None and not response.signals and not response.components:
        raise HTTPException(status_code=404, detail="Robot not found")
    return response
