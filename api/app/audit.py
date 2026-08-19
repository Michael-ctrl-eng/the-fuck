from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from . import models


async def record_audit(
    session: AsyncSession,
    *,
    org_id: str,
    actor_id: str | None,
    action: str,
    resource_type: str = "",
    resource_id: str = "",
    details: dict[str, Any] | None = None,
    ip: str = "",
) -> None:
    session.add(
        models.AuditEvent(
            org_id=org_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip=ip,
        )
    )
