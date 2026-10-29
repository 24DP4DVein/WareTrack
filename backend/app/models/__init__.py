from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="USER")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    activities = relationship("ActivityLog", back_populates="user")
    transfers = relationship("Transfer", back_populates="creator")
    company_memberships = relationship(
        "CompanyMembership", foreign_keys="CompanyMembership.user_id", back_populates="user"
    )
    approved_company_memberships = relationship(
        "CompanyMembership", foreign_keys="CompanyMembership.approved_by_id", back_populates="approved_by"
    )
    revoked_company_memberships = relationship(
        "CompanyMembership", foreign_keys="CompanyMembership.revoked_by_id", back_populates="revoked_by"
    )
    company_join_requests = relationship(
        "CompanyJoinRequest", foreign_keys="CompanyJoinRequest.user_id", back_populates="user"
    )
    reviewed_company_join_requests = relationship(
        "CompanyJoinRequest", foreign_keys="CompanyJoinRequest.reviewed_by_id", back_populates="reviewed_by"
    )


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (Index("ix_companies_active_name", "is_active", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    memberships = relationship("CompanyMembership", back_populates="company")
    join_requests = relationship("CompanyJoinRequest", back_populates="company")
    categories = relationship("Category", back_populates="company")
    suppliers = relationship("Supplier", back_populates="company")
    locations = relationship("Location", back_populates="company")
    items = relationship("Item", back_populates="company")
    transfers = relationship("Transfer", back_populates="company")
    activity_logs = relationship("ActivityLog", back_populates="company")


class CompanyMembership(Base):
    __tablename__ = "company_memberships"
    __table_args__ = (
        UniqueConstraint("company_id", "user_id", name="uq_company_memberships_company_user"),
        CheckConstraint("role IN ('LIETOTAJS', 'VADITAJS')", name="ck_company_memberships_role"),
        Index("ix_company_memberships_user_active", "user_id", "is_active"),
        Index("ix_company_memberships_company_active_role", "company_id", "is_active", "role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="RESTRICT"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    role: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    company = relationship("Company", back_populates="memberships")
    user = relationship("User", foreign_keys=[user_id], back_populates="company_memberships")
    approved_by = relationship(
        "User", foreign_keys=[approved_by_id], back_populates="approved_company_memberships"
    )
    revoked_by = relationship(
        "User", foreign_keys=[revoked_by_id], back_populates="revoked_company_memberships"
    )


class CompanyJoinRequest(Base):
    __tablename__ = "company_join_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED')",
            name="ck_company_join_requests_status",
        ),
        Index(
            "uq_company_join_requests_pending",
            "company_id",
            "user_id",
            unique=True,
            sqlite_where=text("status = 'PENDING'"),
        ),
        Index(
            "ix_company_join_requests_company_status_requested",
            "company_id",
            "status",
            "requested_at",
        ),
        Index(
            "ix_company_join_requests_user_status_requested",
            "user_id",
            "status",
            "requested_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="RESTRICT"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    company = relationship("Company", back_populates="join_requests")
    user = relationship("User", foreign_keys=[user_id], back_populates="company_join_requests")
    reviewed_by = relationship(
        "User", foreign_keys=[reviewed_by_id], back_populates="reviewed_company_join_requests"
    )


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        Index(
            "uq_categories_company_name", "company_id", "name", unique=True,
            sqlite_where=text("company_id IS NOT NULL"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(30), default="Package")
    color: Mapped[str] = mapped_column(String(20), default="blue")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    company = relationship("Company", back_populates="categories")
    items = relationship("Item", back_populates="category")


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        Index(
            "uq_suppliers_company_name", "company_id", "name", unique=True,
            sqlite_where=text("company_id IS NOT NULL"),
        ),
        Index(
            "uq_suppliers_company_email", "company_id", "email", unique=True,
            sqlite_where=text("company_id IS NOT NULL"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(150))
    contact_person: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(30))
    address: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(100), default="Da?Š?üdi")
    payment_terms: Mapped[str] = mapped_column(String(20), default="net30")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    company = relationship("Company", back_populates="suppliers")
    items = relationship("Item", back_populates="supplier")


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (
        Index(
            "uq_locations_company_code", "company_id", "code", unique=True,
            sqlite_where=text("company_id IS NOT NULL"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(120))
    capacity: Mapped[int] = mapped_column(Integer, default=1000)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    company = relationship("Company", back_populates="locations")
    items = relationship("Item", back_populates="location")


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        Index(
            "uq_items_company_sku", "company_id", "sku", unique=True,
            sqlite_where=text("company_id IS NOT NULL"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), index=True)
    sku: Mapped[str] = mapped_column(String(30), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"))
    stock: Mapped[int] = mapped_column(Integer, default=0)
    min_stock: Mapped[int] = mapped_column(Integer, default=0)
    price: Mapped[float] = mapped_column(Float, default=0)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    company = relationship("Company", back_populates="items")
    category = relationship("Category", back_populates="items")
    supplier = relationship("Supplier", back_populates="items")
    location = relationship("Location", back_populates="items")
    transfers = relationship("Transfer", back_populates="item")


class Transfer(Base):
    __tablename__ = "transfers"
    __table_args__ = (UniqueConstraint("code"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(30), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"))
    source_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"))
    destination_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"))
    quantity: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    notes: Mapped[str] = mapped_column(Text, default="")
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    company = relationship("Company", back_populates="transfers")
    item = relationship("Item", back_populates="transfers")
    source_location = relationship("Location", foreign_keys=[source_location_id])
    destination_location = relationship("Location", foreign_keys=[destination_location_id])
    creator = relationship("User", back_populates="transfers")


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id"), nullable=True, index=True
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    message: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    company = relationship("Company", back_populates="activity_logs")
    user = relationship("User", back_populates="activities")

