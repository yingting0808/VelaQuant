import json
from typing import Any
from uuid import UUID

from sqlmodel import Session

from app.domain.models import AuditLog


def record_audit(
    *,
    session: Session,
    team_id: UUID | None,
    user_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: str | None,
    metadata: dict[str, Any],
) -> AuditLog:
    entry = AuditLog(
        team_id=team_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=json.dumps(metadata, ensure_ascii=False, sort_keys=True),
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry
