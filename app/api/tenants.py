import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_tenant
from app.schemas.tenant import TenantCreate, TenantResponse, TenantUpdate
from app.services import tenant_service

router = APIRouter(prefix="/api/tenants", tags=["Tenants"])


@router.post("", response_model=TenantResponse)
async def create_tenant(
    req: TenantCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenant_service.create_tenant(
        db,
        user,
        page_name=req.page_name,
        fb_page_id=req.fb_page_id,
        page_access_token=req.page_access_token,
        website_url=req.website_url,
        business_phone=req.business_phone,
        business_email=req.business_email,
        notification_pref=req.notification_pref,
    )
    return TenantResponse(
        id=str(tenant.id),
        fb_page_id=tenant.fb_page_id,
        page_name=tenant.page_name,
        website_url=tenant.website_url,
        business_phone=tenant.business_phone,
        business_email=tenant.business_email,
        notification_pref=tenant.notification_pref,
        is_active=tenant.is_active,
        created_at=tenant.created_at,
    )


@router.get("", response_model=list[TenantResponse])
async def list_tenants(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenants = await tenant_service.get_user_tenants(db, user)
    return [
        TenantResponse(
            id=str(t.id),
            fb_page_id=t.fb_page_id,
            page_name=t.page_name,
            website_url=t.website_url,
            business_phone=t.business_phone,
            business_email=t.business_email,
            notification_pref=t.notification_pref,
            is_active=t.is_active,
            created_at=t.created_at,
        )
        for t in tenants
    ]


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant_detail(tenant=Depends(get_tenant)):
    return TenantResponse(
        id=str(tenant.id),
        fb_page_id=tenant.fb_page_id,
        page_name=tenant.page_name,
        website_url=tenant.website_url,
        business_phone=tenant.business_phone,
        business_email=tenant.business_email,
        notification_pref=tenant.notification_pref,
        is_active=tenant.is_active,
        created_at=tenant.created_at,
    )


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant_detail(
    req: TenantUpdate,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    updated = await tenant_service.update_tenant(
        db, tenant, **req.model_dump(exclude_none=True)
    )
    return TenantResponse(
        id=str(updated.id),
        fb_page_id=updated.fb_page_id,
        page_name=updated.page_name,
        website_url=updated.website_url,
        business_phone=updated.business_phone,
        business_email=updated.business_email,
        notification_pref=updated.notification_pref,
        is_active=updated.is_active,
        created_at=updated.created_at,
    )


@router.get("/{tenant_id}/stats")
async def get_stats(
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    return await tenant_service.get_tenant_stats(db, tenant.id)
