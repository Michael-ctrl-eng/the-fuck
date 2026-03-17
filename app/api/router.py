from fastapi import APIRouter

from app.api import auth, tenants, products, orders, conversations, crawl, webhook, facebook, test_chat

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(tenants.router)
api_router.include_router(products.router)
api_router.include_router(orders.router)
api_router.include_router(conversations.router)
api_router.include_router(crawl.router)
api_router.include_router(webhook.router)
api_router.include_router(facebook.router)
api_router.include_router(test_chat.router)
