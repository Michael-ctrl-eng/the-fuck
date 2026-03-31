from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_tenant
from app.schemas.order import (
    OrderListResponse, OrderResponse, OrderItemResponse,
    OrderStatusUpdate, ManualOrderCreate, OrderNotesUpdate,
)
from app.services import order_service

router = APIRouter(prefix="/api/tenants/{tenant_id}/orders", tags=["Orders"])


def _order_response(o) -> OrderResponse:
    return OrderResponse(
        id=str(o.id), order_number=o.order_number,
        customer_name=o.customer_name, customer_phone=o.customer_phone,
        division=o.division, district=o.district, upazila=o.upazila,
        address_detail=o.address_detail, payment_method=o.payment_method,
        payment_phone_last2=o.payment_phone_last2,
        payment_trx_id=o.payment_trx_id,
        subtotal=o.subtotal, delivery_charge=o.delivery_charge,
        total=o.total, status=o.status, notes=o.notes,
        created_at=o.created_at,
        items=[
            OrderItemResponse(
                id=str(item.id), product_name=item.product_name,
                quantity=item.quantity, unit_price=item.unit_price,
                total_price=item.total_price,
            )
            for item in o.items
        ],
    )


@router.post("", response_model=OrderResponse, status_code=201)
async def create_manual_order(
    req: ManualOrderCreate,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Create an order manually from the dashboard."""
    from sqlalchemy import select
    from app.models.customer import Customer

    # Find or create customer by phone
    result = await db.execute(
        select(Customer).where(
            Customer.tenant_id == tenant.id,
            Customer.phone == req.customer_phone,
        )
    )
    customer = result.scalar_one_or_none()

    if not customer:
        customer = Customer(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            fb_psid=f"manual-{uuid.uuid4()}",
            name=req.customer_name,
            phone=req.customer_phone,
            division=req.division,
            district=req.district,
            upazila=req.upazila,
            address_detail=req.address_detail,
        )
        db.add(customer)
        await db.flush()
    else:
        customer.name = req.customer_name
        customer.division = req.division
        customer.district = req.district
        customer.upazila = req.upazila
        customer.address_detail = req.address_detail

    items = [
        {
            "product_name": item.product_name,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
        }
        for item in req.items
    ]

    order = await order_service.create_order(
        db=db,
        tenant_id=tenant.id,
        customer_id=customer.id,
        conversation_id=None,
        customer_name=req.customer_name,
        customer_phone=req.customer_phone,
        division=req.division,
        district=req.district,
        upazila=req.upazila,
        address_detail=req.address_detail,
        payment_method=req.payment_method,
        items=items,
        delivery_charge=req.delivery_charge,
        notes=req.notes,
    )

    return _order_response(order)


@router.get("", response_model=OrderListResponse)
async def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    orders, total = await order_service.get_orders(
        db, tenant.id, page, page_size, status
    )
    return OrderListResponse(
        orders=[_order_response(o) for o in orders],
        total=total, page=page, page_size=page_size,
    )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: uuid.UUID,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    order = await order_service.get_order_by_id(db, tenant.id, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _order_response(order)


@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_status(
    order_id: uuid.UUID,
    req: OrderStatusUpdate,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    order = await order_service.get_order_by_id(db, tenant.id, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    try:
        updated = await order_service.update_order_status(db, order, req.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if req.notes:
        existing = updated.notes or ""
        updated.notes = f"{existing}\n[{req.status}] {req.notes}".strip()
        await db.flush()

    return _order_response(updated)


@router.patch("/{order_id}/notes")
async def update_notes(
    order_id: uuid.UUID,
    req: OrderNotesUpdate,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    order = await order_service.get_order_by_id(db, tenant.id, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.notes = req.notes
    await db.flush()
    return {"status": "updated"}


@router.patch("/{order_id}/payment")
async def update_payment_info(
    order_id: uuid.UUID,
    req: dict,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Update payment verification info (bKash/Nagad last 2 digits or trx ID)."""
    order = await order_service.get_order_by_id(db, tenant.id, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if req.get("payment_phone_last2"):
        order.payment_phone_last2 = req["payment_phone_last2"]
    if req.get("payment_trx_id"):
        order.payment_trx_id = req["payment_trx_id"]
    if req.get("payment_method"):
        order.payment_method = req["payment_method"]
    await db.flush()
    return {"status": "updated"}
