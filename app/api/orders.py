from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_tenant
from app.schemas.order import OrderListResponse, OrderResponse, OrderItemResponse, OrderStatusUpdate
from app.services import order_service

router = APIRouter(prefix="/api/tenants/{tenant_id}/orders", tags=["Orders"])


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
        orders=[
            OrderResponse(
                id=str(o.id), order_number=o.order_number,
                customer_name=o.customer_name, customer_phone=o.customer_phone,
                division=o.division, district=o.district, upazila=o.upazila,
                address_detail=o.address_detail, payment_method=o.payment_method,
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
            for o in orders
        ],
        total=total,
        page=page,
        page_size=page_size,
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
    return OrderResponse(
        id=str(order.id), order_number=order.order_number,
        customer_name=order.customer_name, customer_phone=order.customer_phone,
        division=order.division, district=order.district, upazila=order.upazila,
        address_detail=order.address_detail, payment_method=order.payment_method,
        subtotal=order.subtotal, delivery_charge=order.delivery_charge,
        total=order.total, status=order.status, notes=order.notes,
        created_at=order.created_at,
        items=[
            OrderItemResponse(
                id=str(item.id), product_name=item.product_name,
                quantity=item.quantity, unit_price=item.unit_price,
                total_price=item.total_price,
            )
            for item in order.items
        ],
    )


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
    return OrderResponse(
        id=str(updated.id), order_number=updated.order_number,
        customer_name=updated.customer_name, customer_phone=updated.customer_phone,
        division=updated.division, district=updated.district, upazila=updated.upazila,
        address_detail=updated.address_detail, payment_method=updated.payment_method,
        subtotal=updated.subtotal, delivery_charge=updated.delivery_charge,
        total=updated.total, status=updated.status, notes=updated.notes,
        created_at=updated.created_at,
        items=[
            OrderItemResponse(
                id=str(item.id), product_name=item.product_name,
                quantity=item.quantity, unit_price=item.unit_price,
                total_price=item.total_price,
            )
            for item in updated.items
        ],
    )
