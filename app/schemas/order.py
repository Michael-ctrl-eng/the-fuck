from __future__ import annotations

from decimal import Decimal
from pydantic import BaseModel
from datetime import datetime


class OrderItemResponse(BaseModel):
    id: str
    product_name: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: str
    order_number: str
    customer_name: str
    customer_phone: str
    division: str
    district: str
    upazila: str | None
    address_detail: str
    payment_method: str
    subtotal: Decimal
    delivery_charge: Decimal
    total: Decimal
    status: str
    notes: str | None
    created_at: datetime
    items: list[OrderItemResponse] = []

    model_config = {"from_attributes": True}


class OrderListResponse(BaseModel):
    orders: list[OrderResponse]
    total: int
    page: int
    page_size: int


class OrderStatusUpdate(BaseModel):
    status: str

    model_config = {
        "json_schema_extra": {
            "examples": [{"status": "confirmed"}]
        }
    }
