from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.identity import User
from app.models.system import ActivityLog


def log_admin_action(
    db: Session,
    actor: User,
    action: str,
    target_type: str,
    target_id: str | int,
    *,
    reason: str,
    before: Any = None,
    after: Any = None,
) -> ActivityLog:
    """Every admin mutation goes through here: who, when, what changed and why."""
    if not reason or not reason.strip():
        raise HTTPException(422, "A reason is required for this action.")
    entry = ActivityLog(
        actor_id=actor.id,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        before=before,
        after=after,
        reason=reason.strip(),
    )
    db.add(entry)
    db.flush()
    return entry
