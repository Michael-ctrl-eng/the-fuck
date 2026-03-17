import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.models.user import User


async def create_tenant(db: AsyncSession, owner: User, **kwargs) -> Tenant:
    tenant = Tenant(id=uuid.uuid4(), owner_id=owner.id, **kwargs)
    db.add(tenant)
    await db.flush()
    return tenant


async def get_user_tenants(db: AsyncSession, user: User) -> list[Tenant]:
    result = await db.execute(
        select(Tenant).where(Tenant.owner_id == user.id, Tenant.is_active == True)
    )
    return list(result.scalars().all())


async def update_tenant(db: AsyncSession, tenant: Tenant, **kwargs) -> Tenant:
    for key, value in kwargs.items():
        if value is not None and hasattr(tenant, key):
            setattr(tenant, key, value)
    await db.flush()
    return tenant


async def get_tenant_stats(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    from app.models.product import Product
    from app.models.order import Order
    from app.models.conversation import Conversation

    products_count = await db.scalar(
        select(func.count(Product.id)).where(
            Product.tenant_id == tenant_id, Product.is_active == True
        )
    )
    orders_count = await db.scalar(
        select(func.count(Order.id)).where(Order.tenant_id == tenant_id)
    )
    pending_orders = await db.scalar(
        select(func.count(Order.id)).where(
            Order.tenant_id == tenant_id, Order.status == "pending"
        )
    )
    active_conversations = await db.scalar(
        select(func.count(Conversation.id)).where(
            Conversation.tenant_id == tenant_id, Conversation.status == "active"
        )
    )
    total_revenue = await db.scalar(
        select(func.coalesce(func.sum(Order.total), 0)).where(
            Order.tenant_id == tenant_id,
            Order.status.in_(["confirmed", "shipped", "delivered"]),
        )
    )

    return {
        "products_count": products_count or 0,
        "orders_count": orders_count or 0,
        "pending_orders": pending_orders or 0,
        "active_conversations": active_conversations or 0,
        "total_revenue": float(total_revenue or 0),
    }
