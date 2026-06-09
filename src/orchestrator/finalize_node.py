from datetime import datetime, timezone

from sqlmodel import Session

from db import get_engine
from logging_config import get_logger
from models import Run
from orchestrator.state import OrchestratorState

log = get_logger(__name__)


def finalize_node(state: OrchestratorState) -> OrchestratorState:
    """Marks the Run completed or failed and stamps completed_at."""

    run_id = state.get("run_id")
    if not run_id:
        return {}

    failed = bool(state.get("is_fatal_error"))
    outcomes = state.get("outcomes") or []
    if outcomes and all(o.get("status") == "failed" for o in outcomes):
        failed = True

    status = "failed" if failed else "completed"
    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        if run:
            run.status = status
            run.completed_at = datetime.now(timezone.utc)
            session.add(run)
            session.commit()

    log.info("run.finalized", run_id=run_id, status=status)
    return {}
