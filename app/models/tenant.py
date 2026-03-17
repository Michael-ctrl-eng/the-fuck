import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    fb_page_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True)
    page_name: Mapped[str] = mapped_column(String(255))
    page_access_token: Mapped[Optional[str]] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    website_url: Mapped[Optional[str]] = mapped_column(String(512))
    business_phone: Mapped[Optional[str]] = mapped_column(String(20))
    business_email: Mapped[Optional[str]] = mapped_column(String(255))
    notification_pref: Mapped[str] = mapped_column(String(20), default="email")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    owner = relationship("User", back_populates="tenants")
    products = relationship("Product", back_populates="tenant", cascade="all, delete-orphan")
    customers = relationship("Customer", back_populates="tenant", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="tenant", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="tenant", cascade="all, delete-orphan")
    crawl_jobs = relationship("CrawlJob", back_populates="tenant", cascade="all, delete-orphan")
    knowledge_base = relationship("KnowledgeBase", back_populates="tenant", uselist=False)
