from datetime import datetime, timezone

from sqlmodel import Session

from db import get_engine
from models import Run
from orchestrator.state import OrchestratorState


def finalize_node(state: OrchestratorState) -> OrchestratorState:
    """Marks the Run completed or failed and stamps completed_at."""

    run_id = state.get("run_id")
    if not run_id:
        return {}

    failed = bool(state.get("is_fatal_error"))
    outcomes = state.get("outcomes") or []
    if outcomes and all(o.get("status") == "failed" for o in outcomes):
        failed = True

    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        if run:
            run.status = "failed" if failed else "completed"
            run.completed_at = datetime.now(timezone.utc)
            session.add(run)
            session.commit()

    return {}
