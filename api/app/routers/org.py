from __future__ import annotations

import re
import secrets

from fastapi import APIRouter, Request
from sqlalchemy import select

from .. import models
from ..audit import record_audit
from ..deps import DbDep, MembershipDep, OrgDep, UserDep, csrf_dep, require_role
from ..errors import ConflictError, NotFoundError, PermissionError
from ..schemas import (
    CreateOrgRequest,
    MemberInviteRequest,
    MemberOut,
    MemberRoleUpdate,
    OrgOut,
)
router = APIRouter(prefix="/api/orgs", tags=["orgs"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]
    return slug or "org"


async def _orgs_for(db, user_id: str) -> list[OrgOut]:
    rows = await db.execute(
        select(models.OrgMembership).where(models.OrgMembership.user_id == user_id)
    )
    out = []
    for m in rows.scalars().all():
        org = await db.get(models.Organization, m.org_id)
        if org is None:
            continue
        count = (
            await db.execute(
                select(models.OrgMembership).where(models.OrgMembership.org_id == org.id)
            )
        ).scalars().all()
        out.append(OrgOut(
            id=org.id, name=org.name, slug=org.slug, role=m.role,
            members_count=len(count), created_at=org.created_at,
        ))
    return out


@router.get("", response_model=list[OrgOut])
async def list_orgs(db: DbDep, user: UserDep):
    return await _orgs_for(db, user.id)


@router.post("", response_model=OrgOut, dependencies=[csrf_dep])
async def create_org(body: CreateOrgRequest, db: DbDep, user: UserDep, request: Request, membership: MembershipDep):
    org = models.Organization(
        name=body.name.strip(),
        slug=f"{_slugify(body.name)}-{secrets.token_hex(3)}",
    )
    db.add(org)
    await db.flush()
    db.add(models.OrgMembership(org_id=org.id, user_id=user.id, role="owner"))
    await record_audit(db, org_id=org.id, actor_id=user.id, action="org.create",
                       resource_type="org", resource_id=org.id, ip=request.client.host if request.client else "")
    await db.commit()
    return OrgOut(id=org.id, name=org.name, slug=org.slug, role="owner", members_count=1, created_at=org.created_at)


@router.get("/current/members", response_model=list[MemberOut])
async def list_members(db: DbDep, org: OrgDep, membership: MembershipDep):
    rows = await db.execute(
        select(models.OrgMembership)
        .where(models.OrgMembership.org_id == org.id)
        .order_by(models.OrgMembership.created_at)
    )
    out = []
    for m in rows.scalars().all():
        user = await db.get(models.User, m.user_id)
        if user is None:
            continue
        out.append(MemberOut(
            id=m.id, user_id=m.user_id, email=user.email, full_name=user.full_name,
            role=m.role, created_at=m.created_at,
        ))
    return out


@router.post("/current/members", response_model=MemberOut, dependencies=[csrf_dep])
async def invite_member(body: MemberInviteRequest, db: DbDep, org: OrgDep, membership: MembershipDep, request: Request):
    if membership.role not in ("owner", "admin"):
        raise PermissionError()
    target = (
        await db.execute(select(models.User).where(models.User.email == body.email.lower()))
    ).scalar_one_or_none()
    if target is None:
        raise NotFoundError("لا يوجد حساب بهذا البريد — يجب أن يسجّل المستخدم حسابًا أولًا")
    if target.id == membership.user_id:
        raise ConflictError("لا يمكن إضافة نفسك")
    existing = (
        await db.execute(
            select(models.OrgMembership).where(
                models.OrgMembership.org_id == org.id,
                models.OrgMembership.user_id == target.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError("المستخدم عضو بالفعل")
    rank = {"owner": 0, "admin": 1, "moderator": 2, "viewer": 3}
    if rank[body.role] < rank[membership.role]:
        raise PermissionError("لا يمكنك منح صلاحية أعلى من صلاحيتك")
    row = models.OrgMembership(org_id=org.id, user_id=target.id, role=body.role)
    db.add(row)
    await record_audit(db, org_id=org.id, actor_id=membership.user_id, action="member.invite",
                       resource_type="membership", resource_id=row.id, ip=request.client.host if request.client else "")
    await db.commit()
    return MemberOut(id=row.id, user_id=target.id, email=target.email,
                     full_name=target.full_name, role=row.role, created_at=row.created_at)


@router.patch("/current/members/{membership_id}", response_model=MemberOut, dependencies=[csrf_dep])
async def update_member_role(membership_id: str, body: MemberRoleUpdate, db: DbDep, org: OrgDep, membership: MembershipDep, request: Request):
    if membership.role != "owner":
        raise PermissionError("تغيير الأدوار متاح للمالك فقط")
    row = await db.get(models.OrgMembership, membership_id)
    if row is None or row.org_id != org.id:
        raise NotFoundError("العضو غير موجود")
    if row.role == "owner" and body.role != "owner":
        owners = (
            await db.execute(
                select(models.OrgMembership).where(
                    models.OrgMembership.org_id == org.id,
                    models.OrgMembership.role == "owner",
                )
            )
        ).scalars().all()
        if len(owners) <= 1:
            raise ConflictError("لا يمكن إزالة المالك الوحيد")
    row.role = body.role
    await record_audit(db, org_id=org.id, actor_id=membership.user_id, action="member.role",
                       resource_type="membership", resource_id=row.id, details={"role": body.role},
                       ip=request.client.host if request.client else "")
    await db.commit()
    user = await db.get(models.User, row.user_id)
    return MemberOut(id=row.id, user_id=row.user_id, email=user.email if user else "",
                     full_name=user.full_name if user else "", role=row.role, created_at=row.created_at)


@router.delete("/current/members/{membership_id}", dependencies=[csrf_dep])
async def remove_member(membership_id: str, db: DbDep, org: OrgDep, membership: MembershipDep, request: Request):
    if membership.role != "owner":
        raise PermissionError("إزالة الأعضاء متاحة للمالك فقط")
    row = await db.get(models.OrgMembership, membership_id)
    if row is None or row.org_id != org.id:
        raise NotFoundError("العضو غير موجود")
    if row.user_id == membership.user_id:
        raise ConflictError("لا يمكنك إزالة نفسك — انقل الملكية أولًا")
    if row.role == "owner":
        owners = (
            await db.execute(
                select(models.OrgMembership).where(
                    models.OrgMembership.org_id == org.id,
                    models.OrgMembership.role == "owner",
                )
            )
        ).scalars().all()
        if len(owners) <= 1:
            raise ConflictError("لا يمكن إزالة المالك الوحيد")
    await record_audit(db, org_id=org.id, actor_id=membership.user_id, action="member.remove",
                       resource_type="membership", resource_id=row.id, ip=request.client.host if request.client else "")
    await db.delete(row)
    await db.commit()
    return {"ok": True}
