"""Seed the database with a test user, tenant, and sample Bangladeshi products."""
import asyncio
import uuid
from decimal import Decimal

from app.database import async_session
from app.models.user import User
from app.models.tenant import Tenant
from app.models.product import Product
from app.utils.security import hash_password


async def seed():
    async with async_session() as db:
        # Create test user
        user = User(
            id=uuid.uuid4(),
            name="Jubair",
            email="jubair@test.com",
            hashed_password=hash_password("test123"),
        )
        db.add(user)
        await db.flush()

        # Create tenant
        tenant = Tenant(
            id=uuid.uuid4(),
            owner_id=user.id,
            page_name="Mama Fashion House",
            fb_page_id="mama_fashion_123",
            website_url="https://mamafashion.com",
            business_email="jubair@test.com",
            business_phone="01712345678",
            notification_pref="email",
        )
        db.add(tenant)
        await db.flush()

        # Bangladeshi products — each with different attribute formats
        products = [
            # Sarees — with material, color, origin
            Product(id=uuid.uuid4(), tenant_id=tenant.id, source="manual",
                name="Jamdani Saree", price=Decimal("8500.00"), attributes={
                    "name_bn": "জামদানি শাড়ি", "description": "Authentic Dhaka Jamdani saree with traditional muslin weave.",
                    "discount_price": 7200, "category": "Saree", "sku": "SAR-JAM-001",
                    "stock_status": "in_stock", "material": "muslin", "color": "white & gold", "origin": "Dhaka",
                }),
            Product(id=uuid.uuid4(), tenant_id=tenant.id, source="manual",
                name="Cotton Tant Saree", price=Decimal("1500.00"), attributes={
                    "name_bn": "সুতি তাঁত শাড়ি", "description": "Lightweight cotton tant saree for daily wear.",
                    "discount_price": 1200, "category": "Saree", "sku": "SAR-TAN-001",
                    "stock_status": "in_stock", "material": "cotton", "origin": "Tangail",
                }),
            Product(id=uuid.uuid4(), tenant_id=tenant.id, source="manual",
                name="Silk Katan Saree", price=Decimal("12000.00"), attributes={
                    "name_bn": "সিল্ক কাতান শাড়ি", "description": "Premium Rajshahi silk with golden zari border.",
                    "category": "Saree", "sku": "SAR-KAT-001", "stock_status": "in_stock",
                    "material": "silk", "color": "red & gold", "origin": "Rajshahi",
                }),
            Product(id=uuid.uuid4(), tenant_id=tenant.id, source="manual",
                name="Muslin Saree", price=Decimal("15000.00"), attributes={
                    "name_bn": "মসলিন শাড়ি", "description": "Dhakai muslin, ultra-soft. Heritage craft.",
                    "discount_price": 13500, "category": "Saree", "sku": "SAR-MUS-001",
                    "stock_status": "limited", "material": "muslin", "origin": "Dhaka",
                }),

            # Punjabis — with size info
            Product(id=uuid.uuid4(), tenant_id=tenant.id, source="manual",
                name="Silk Punjabi", price=Decimal("3500.00"), attributes={
                    "name_bn": "সিল্ক পাঞ্জাবি", "description": "Elegant silk punjabi for Eid.",
                    "discount_price": 2800, "category": "Punjabi", "sku": "PUN-SIL-001",
                    "stock_status": "in_stock", "material": "silk", "sizes": "M, L, XL, XXL",
                }),
            Product(id=uuid.uuid4(), tenant_id=tenant.id, source="manual",
                name="Cotton Panjabi", price=Decimal("1200.00"), attributes={
                    "name_bn": "সুতি পাঞ্জাবি", "description": "Casual cotton panjabi. Multiple colors.",
                    "category": "Punjabi", "stock_status": "in_stock", "material": "cotton",
                    "sizes": "S, M, L, XL", "colors": "white, blue, green",
                }),
            Product(id=uuid.uuid4(), tenant_id=tenant.id, source="manual",
                name="Fatua", price=Decimal("900.00"), attributes={
                    "name_bn": "ফতুয়া", "description": "Traditional fatua with embroidery.",
                    "category": "Punjabi", "stock_status": "in_stock", "material": "cotton blend",
                }),

            # Home & Accessories — varied attributes
            Product(id=uuid.uuid4(), tenant_id=tenant.id, source="manual",
                name="Nakshi Kantha", price=Decimal("2500.00"), attributes={
                    "name_bn": "নকশি কাঁথা", "description": "Handstitched nakshi kantha. Perfect gift.",
                    "category": "Home Decor", "stock_status": "in_stock",
                    "size": "60x90 inches", "craft": "hand-embroidered",
                }),
            Product(id=uuid.uuid4(), tenant_id=tenant.id, source="manual",
                name="Leather Wallet", price=Decimal("800.00"), attributes={
                    "name_bn": "চামড়ার মানিব্যাগ", "description": "Genuine leather wallet from Old Dhaka.",
                    "discount_price": 650, "category": "Accessories", "stock_status": "in_stock",
                    "material": "genuine leather", "card_slots": 8, "color": "brown",
                }),
            Product(id=uuid.uuid4(), tenant_id=tenant.id, source="manual",
                name="Jute Bag", price=Decimal("450.00"), attributes={
                    "name_bn": "পাটের ব্যাগ", "description": "Eco-friendly jute tote with traditional prints.",
                    "category": "Accessories", "stock_status": "in_stock",
                    "material": "jute", "eco_friendly": True,
                }),
            Product(id=uuid.uuid4(), tenant_id=tenant.id, source="manual",
                name="Brass Jewelry Set", price=Decimal("1800.00"), attributes={
                    "name_bn": "পিতলের গহনা সেট", "description": "Traditional brass necklace and earring set.",
                    "discount_price": 1500, "category": "Jewelry", "stock_status": "in_stock",
                    "material": "brass", "finish": "oxidized", "pieces": "necklace + earrings",
                }),
            Product(id=uuid.uuid4(), tenant_id=tenant.id, source="manual",
                name="Nokshi Slipper", price=Decimal("550.00"), attributes={
                    "name_bn": "নকশি স্লিপার", "description": "Hand-decorated leather slipper with nokshi art.",
                    "category": "Footwear", "stock_status": "out_of_stock",
                    "material": "leather", "sizes": "6, 7, 8, 9, 10",
                }),
        ]

        for p in products:
            db.add(p)

        await db.commit()

        print(f"\n{'='*50}")
        print(f"Seed completed!")
        print(f"{'='*50}")
        print(f"User email:    jubair@test.com")
        print(f"User password: test123")
        print(f"Tenant:        Mama Fashion House")
        print(f"Tenant ID:     {tenant.id}")
        print(f"Products:      {len(products)} items seeded")
        print(f"{'='*50}")
        print(f"\nOpen http://localhost:8000/dashboard/login")
        print(f"Login and start chatting!\n")


if __name__ == "__main__":
    asyncio.run(seed())
